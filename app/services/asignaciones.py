"""Reglas de disponibilidad y asignación de equipos."""
import uuid
from datetime import datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from ..enums import EstadoAsignacion, EstadoEquipo, TipoEquipo
from ..errors import ReglaNegocioError
from ..models import Asignacion, Equipo, Mantenimiento, Usuario
from ..schemas import AsignacionCrear, SolicitudAsignacion
from . import auditoria


def _asignacion_cruzada(inicio: datetime, fin: datetime):
    """Dos periodos se cruzan si cada uno empieza antes de que termine el otro."""
    return and_(
        Asignacion.estado == EstadoAsignacion.activa,
        Asignacion.inicio < fin,
        Asignacion.fin > inicio,
    )


def _mantenimiento_cruzado(inicio: datetime, fin: datetime):
    return and_(
        Mantenimiento.inicio < fin,
        or_(Mantenimiento.fin.is_(None), Mantenimiento.fin > inicio),
    )


def equipos_disponibles(
    db: Session,
    inicio: datetime,
    fin: datetime,
    *,
    zona_id: int | None = None,
    tipo: TipoEquipo | None = None,
    ram_min: int | None = None,
    almacenamiento_min: int | None = None,
    software: list[str] | None = None,
) -> list[Equipo]:
    """Equipos operativos, sin asignación ni mantenimiento que se cruce con el periodo.

    Se devuelven ordenados por criterio de uso equilibrado: primero los que
    menos asignaciones han tenido, para repartir el desgaste entre los equipos.
    """
    ocupado = exists().where(Asignacion.equipo_id == Equipo.id, _asignacion_cruzada(inicio, fin))
    en_mantenimiento = exists().where(Mantenimiento.equipo_id == Equipo.id, _mantenimiento_cruzado(inicio, fin))
    consulta = select(Equipo).where(
        Equipo.activo.is_(True),
        Equipo.estado == EstadoEquipo.disponible,
        ~ocupado,
        ~en_mantenimiento,
    )
    if zona_id is not None:
        consulta = consulta.where(Equipo.zona_id == zona_id)
    if tipo is not None:
        consulta = consulta.where(Equipo.tipo == tipo)
    if ram_min is not None:
        consulta = consulta.where(Equipo.ram_gb >= ram_min)
    if almacenamiento_min is not None:
        consulta = consulta.where(Equipo.almacenamiento_gb >= almacenamiento_min)

    equipos = list(db.scalars(consulta).unique())

    if software:
        requeridos = {s.strip().lower() for s in software if s.strip()}
        equipos = [e for e in equipos if requeridos <= {s.lower() for s in (e.software or [])}]

    usos = dict(
        db.execute(
            select(Asignacion.equipo_id, func.count())
            .where(Asignacion.estado == EstadoAsignacion.activa)
            .group_by(Asignacion.equipo_id)
        ).all()
    )
    equipos.sort(key=lambda e: (usos.get(e.id, 0), e.codigo))
    return equipos


def verificar_asignable(db: Session, equipo: Equipo, inicio: datetime, fin: datetime) -> None:
    """Lanza ReglaNegocioError si el equipo no puede asignarse en ese periodo."""
    if not equipo.activo:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} está desactivado")
    if equipo.estado == EstadoEquipo.fuera_de_servicio:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} está fuera de servicio")
    if equipo.estado == EstadoEquipo.en_mantenimiento:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} está en mantenimiento")

    conflictos = list(
        db.scalars(
            select(Asignacion.id).where(Asignacion.equipo_id == equipo.id, _asignacion_cruzada(inicio, fin))
        )
    )
    if conflictos:
        raise ReglaNegocioError(
            f"El equipo {equipo.codigo} ya tiene una asignación que se cruza con el periodo solicitado",
            info={"asignaciones_en_conflicto": conflictos},
        )
    if db.scalar(
        select(Mantenimiento.id).where(Mantenimiento.equipo_id == equipo.id, _mantenimiento_cruzado(inicio, fin))
    ):
        raise ReglaNegocioError(f"El equipo {equipo.codigo} tiene un mantenimiento que se cruza con el periodo")


def crear_asignacion(db: Session, usuario: Usuario, datos: AsignacionCrear, equipo: Equipo) -> Asignacion:
    verificar_asignable(db, equipo, datos.inicio, datos.fin)
    asignacion = Asignacion(
        equipo_id=equipo.id,
        usuario_id=usuario.id,
        actividad=datos.actividad,
        inicio=datos.inicio,
        fin=datos.fin,
    )
    db.add(asignacion)
    db.flush()
    auditoria.registrar(db, usuario, "crear", "asignacion", asignacion.id, f"equipo={equipo.codigo}")
    return asignacion


def seleccionar_equipos(db: Session, datos: SolicitudAsignacion) -> tuple[list[Equipo], int]:
    """Elige equipos para una solicitud. Devuelve (elegidos, total de compatibles disponibles)."""
    filtros = dict(
        tipo=datos.tipo,
        ram_min=datos.ram_min,
        almacenamiento_min=datos.almacenamiento_min,
        software=datos.software,
    )
    if datos.zona_id is not None:
        candidatos = equipos_disponibles(db, datos.inicio, datos.fin, zona_id=datos.zona_id, **filtros)
        if len(candidatos) < datos.cantidad and datos.permitir_otras_zonas:
            ya = {e.id for e in candidatos}
            candidatos += [e for e in equipos_disponibles(db, datos.inicio, datos.fin, **filtros) if e.id not in ya]
    else:
        candidatos = equipos_disponibles(db, datos.inicio, datos.fin, **filtros)
    return candidatos[: datos.cantidad], len(candidatos)


def crear_solicitud(db: Session, usuario: Usuario, datos: SolicitudAsignacion) -> list[Asignacion]:
    elegidos, total = seleccionar_equipos(db, datos)
    if len(elegidos) < datos.cantidad:
        raise ReglaNegocioError(
            "No hay suficientes equipos compatibles disponibles para el periodo solicitado",
            info={"solicitados": datos.cantidad, "disponibles_compatibles": total},
        )
    grupo = str(uuid.uuid4())
    asignaciones = [
        Asignacion(
            equipo_id=e.id,
            usuario_id=usuario.id,
            actividad=datos.actividad,
            inicio=datos.inicio,
            fin=datos.fin,
            grupo=grupo,
        )
        for e in elegidos
    ]
    db.add_all(asignaciones)
    db.flush()
    auditoria.registrar(
        db, usuario, "crear_solicitud", "asignacion", None, f"grupo={grupo}; equipos={len(asignaciones)}"
    )
    return asignaciones
