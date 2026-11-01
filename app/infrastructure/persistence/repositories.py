"""Adaptadores de persistencia: implementan los puertos `*Repository` del dominio con SQLAlchemy."""
from dataclasses import fields
from datetime import datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from ...domain.asignaciones.entities import Asignacion, CriteriosDisponibilidad
from ...domain.identidad.entities import Usuario
from ...domain.inventario.entities import Equipo, Zona
from ...domain.mantenimiento.entities import Incidente, Mantenimiento
from ...domain.mantenimiento.policies import SEVERIDADES_BLOQUEANTES
from ...domain.shared.enums import EstadoAsignacion, EstadoEquipo, EstadoIncidente, Severidad, TipoEquipo
from ...domain.shared.ports import RegistroAuditoria
from .orm import (
    AsignacionORM,
    AuditoriaORM,
    EquipoORM,
    IncidenteORM,
    MantenimientoORM,
    UsuarioORM,
    ZonaORM,
)


class _RepositorioSQL:
    """Convierte entre entidades del dominio (dataclasses) y filas ORM."""

    modelo: type
    entidad: type

    def __init__(self, session: Session):
        self._s = session

    def _a_entidad(self, orm):
        if orm is None:
            return None
        return self.entidad(**{f.name: getattr(orm, f.name) for f in fields(self.entidad)})

    def _entidades(self, filas) -> list:
        return [self._a_entidad(f) for f in filas]

    def obtener(self, id_: int):
        return self._a_entidad(self._s.get(self.modelo, id_))

    def guardar(self, entidad):
        """Inserta (id None) o actualiza. Refleja en la entidad los valores generados (id, fechas)."""
        campos = {f.name: getattr(entidad, f.name) for f in fields(entidad) if f.name != "id"}
        if entidad.id is None:
            orm = self.modelo(**{k: v for k, v in campos.items() if v is not None})
            self._s.add(orm)
        else:
            orm = self._s.get(self.modelo, entidad.id)
            for nombre, valor in campos.items():
                setattr(orm, nombre, valor)
        self._s.flush()
        for f in fields(entidad):
            setattr(entidad, f.name, getattr(orm, f.name))
        return entidad

    def contar(self) -> int:
        return self._s.scalar(select(func.count()).select_from(self.modelo))


class SqlUsuarioRepository(_RepositorioSQL):
    modelo, entidad = UsuarioORM, Usuario

    def por_email(self, email: str) -> Usuario | None:
        return self._a_entidad(self._s.scalar(select(UsuarioORM).where(UsuarioORM.email == email)))

    def listar(self, skip: int, limit: int) -> list[Usuario]:
        return self._entidades(self._s.scalars(select(UsuarioORM).order_by(UsuarioORM.id).offset(skip).limit(limit)))


class SqlZonaRepository(_RepositorioSQL):
    modelo, entidad = ZonaORM, Zona

    def por_nombre(self, nombre: str) -> Zona | None:
        return self._a_entidad(self._s.scalar(select(ZonaORM).where(ZonaORM.nombre == nombre)))

    def listar(self) -> list[Zona]:
        return self._entidades(self._s.scalars(select(ZonaORM).order_by(ZonaORM.nombre)))


class SqlEquipoRepository(_RepositorioSQL):
    modelo, entidad = EquipoORM, Equipo

    def por_codigo(self, codigo: str) -> Equipo | None:
        return self._a_entidad(self._s.scalar(select(EquipoORM).where(EquipoORM.codigo == codigo)))

    def listar(
        self,
        zona_id: int | None,
        tipo: TipoEquipo | None,
        estado: EstadoEquipo | None,
        activo: bool,
        skip: int,
        limit: int,
    ) -> list[Equipo]:
        consulta = select(EquipoORM).where(EquipoORM.activo.is_(activo)).order_by(EquipoORM.codigo)
        if zona_id is not None:
            consulta = consulta.where(EquipoORM.zona_id == zona_id)
        if tipo is not None:
            consulta = consulta.where(EquipoORM.tipo == tipo)
        if estado is not None:
            consulta = consulta.where(EquipoORM.estado == estado)
        return self._entidades(self._s.scalars(consulta.offset(skip).limit(limit)))

    def listar_activos(self) -> list[Equipo]:
        return self._entidades(self._s.scalars(select(EquipoORM).where(EquipoORM.activo.is_(True)).order_by(EquipoORM.codigo)))

    def todos(self) -> list[Equipo]:
        return self._entidades(self._s.scalars(select(EquipoORM).order_by(EquipoORM.codigo)))


def _asignacion_cruzada(inicio: datetime, fin: datetime):
    """Dos periodos se cruzan si cada uno empieza antes de que termine el otro."""
    return and_(
        AsignacionORM.estado == EstadoAsignacion.activa,
        AsignacionORM.inicio < fin,
        AsignacionORM.fin > inicio,
    )


class SqlAsignacionRepository(_RepositorioSQL):
    modelo, entidad = AsignacionORM, Asignacion

    def guardar_varias(self, asignaciones: list[Asignacion]) -> list[Asignacion]:
        return [self.guardar(a) for a in asignaciones]

    def listar(
        self,
        equipo_id: int | None,
        estado: EstadoAsignacion | None,
        desde: datetime | None,
        hasta: datetime | None,
        skip: int,
        limit: int,
    ) -> list[Asignacion]:
        consulta = select(AsignacionORM).order_by(AsignacionORM.inicio.desc())
        if equipo_id is not None:
            consulta = consulta.where(AsignacionORM.equipo_id == equipo_id)
        if estado is not None:
            consulta = consulta.where(AsignacionORM.estado == estado)
        if desde is not None:
            consulta = consulta.where(AsignacionORM.fin > desde)
        if hasta is not None:
            consulta = consulta.where(AsignacionORM.inicio < hasta)
        return self._entidades(self._s.scalars(consulta.offset(skip).limit(limit)))

    def ids_en_conflicto(self, equipo_id: int, inicio: datetime, fin: datetime) -> list[int]:
        return list(
            self._s.scalars(
                select(AsignacionORM.id).where(AsignacionORM.equipo_id == equipo_id, _asignacion_cruzada(inicio, fin))
            )
        )

    def pendientes_futuras(self, equipo_id: int, desde: datetime) -> list[int]:
        return list(
            self._s.scalars(
                select(AsignacionORM.id).where(
                    AsignacionORM.equipo_id == equipo_id,
                    AsignacionORM.estado == EstadoAsignacion.activa,
                    AsignacionORM.fin > desde,
                )
            )
        )

    def activas_en_rango(self, desde: datetime, hasta: datetime) -> list[Asignacion]:
        return self._entidades(
            self._s.scalars(
                select(AsignacionORM).where(
                    AsignacionORM.estado == EstadoAsignacion.activa,
                    AsignacionORM.inicio < hasta,
                    AsignacionORM.fin > desde,
                )
            )
        )

    def contar_en_curso(self, ahora: datetime) -> int:
        return self._s.scalar(
            select(func.count())
            .select_from(AsignacionORM)
            .where(
                AsignacionORM.estado == EstadoAsignacion.activa,
                AsignacionORM.inicio <= ahora,
                AsignacionORM.fin > ahora,
            )
        )

    def equipos_disponibles(self, criterios: CriteriosDisponibilidad) -> list[Equipo]:
        inicio, fin = criterios.inicio, criterios.fin
        ocupado = exists().where(AsignacionORM.equipo_id == EquipoORM.id, _asignacion_cruzada(inicio, fin))
        en_mantenimiento = exists().where(
            MantenimientoORM.equipo_id == EquipoORM.id,
            MantenimientoORM.inicio < fin,
            or_(MantenimientoORM.fin.is_(None), MantenimientoORM.fin > inicio),
        )
        consulta = select(EquipoORM).where(
            EquipoORM.activo.is_(True),
            EquipoORM.estado == EstadoEquipo.disponible,
            ~ocupado,
            ~en_mantenimiento,
        )
        if criterios.zona_id is not None:
            consulta = consulta.where(EquipoORM.zona_id == criterios.zona_id)
        if criterios.tipo is not None:
            consulta = consulta.where(EquipoORM.tipo == criterios.tipo)
        if criterios.ram_min is not None:
            consulta = consulta.where(EquipoORM.ram_gb >= criterios.ram_min)
        if criterios.almacenamiento_min is not None:
            consulta = consulta.where(EquipoORM.almacenamiento_gb >= criterios.almacenamiento_min)

        equipos = [SqlEquipoRepository(self._s)._a_entidad(f) for f in self._s.scalars(consulta)]
        if criterios.software:
            requeridos = {s.strip().lower() for s in criterios.software if s.strip()}
            equipos = [e for e in equipos if requeridos <= {s.lower() for s in (e.software or [])}]

        usos = dict(
            self._s.execute(
                select(AsignacionORM.equipo_id, func.count())
                .where(AsignacionORM.estado == EstadoAsignacion.activa)
                .group_by(AsignacionORM.equipo_id)
            ).all()
        )
        equipos.sort(key=lambda e: (usos.get(e.id, 0), e.codigo))
        return equipos


class SqlIncidenteRepository(_RepositorioSQL):
    modelo, entidad = IncidenteORM, Incidente

    def listar(
        self,
        equipo_id: int | None,
        estado: EstadoIncidente | None,
        severidad: Severidad | None,
        skip: int,
        limit: int,
    ) -> list[Incidente]:
        consulta = select(IncidenteORM).order_by(IncidenteORM.fecha_reporte.desc())
        if equipo_id is not None:
            consulta = consulta.where(IncidenteORM.equipo_id == equipo_id)
        if estado is not None:
            consulta = consulta.where(IncidenteORM.estado == estado)
        if severidad is not None:
            consulta = consulta.where(IncidenteORM.severidad == severidad)
        return self._entidades(self._s.scalars(consulta.offset(skip).limit(limit)))

    def contar_graves_abiertos(self, equipo_id: int) -> int:
        self._s.flush()
        return self._s.scalar(
            select(func.count())
            .select_from(IncidenteORM)
            .where(
                IncidenteORM.equipo_id == equipo_id,
                IncidenteORM.estado != EstadoIncidente.resuelto,
                IncidenteORM.severidad.in_(SEVERIDADES_BLOQUEANTES),
            )
        )

    def contar_abiertos(self) -> int:
        return self._s.scalar(
            select(func.count()).select_from(IncidenteORM).where(IncidenteORM.estado != EstadoIncidente.resuelto)
        )

    def reportados_en_rango(self, desde: datetime, hasta: datetime) -> list[Incidente]:
        return self._entidades(
            self._s.scalars(
                select(IncidenteORM).where(IncidenteORM.fecha_reporte >= desde, IncidenteORM.fecha_reporte < hasta)
            )
        )


class SqlMantenimientoRepository(_RepositorioSQL):
    modelo, entidad = MantenimientoORM, Mantenimiento

    def listar(self, equipo_id: int | None, abiertos: bool | None, skip: int, limit: int) -> list[Mantenimiento]:
        consulta = select(MantenimientoORM).order_by(MantenimientoORM.inicio.desc())
        if equipo_id is not None:
            consulta = consulta.where(MantenimientoORM.equipo_id == equipo_id)
        if abiertos is True:
            consulta = consulta.where(MantenimientoORM.fin.is_(None))
        elif abiertos is False:
            consulta = consulta.where(MantenimientoORM.fin.is_not(None))
        return self._entidades(self._s.scalars(consulta.offset(skip).limit(limit)))

    def contar_abiertos_de_equipo(self, equipo_id: int) -> int:
        self._s.flush()
        return self._s.scalar(
            select(func.count())
            .select_from(MantenimientoORM)
            .where(MantenimientoORM.equipo_id == equipo_id, MantenimientoORM.fin.is_(None))
        )

    def contar_abiertos(self) -> int:
        return self._s.scalar(select(func.count()).select_from(MantenimientoORM).where(MantenimientoORM.fin.is_(None)))

    def hay_cruce(self, equipo_id: int, inicio: datetime, fin: datetime) -> bool:
        return (
            self._s.scalar(
                select(MantenimientoORM.id).where(
                    MantenimientoORM.equipo_id == equipo_id,
                    MantenimientoORM.inicio < fin,
                    or_(MantenimientoORM.fin.is_(None), MantenimientoORM.fin > inicio),
                )
            )
            is not None
        )

    def abiertos_iniciados_antes_de(self, limite: datetime) -> list[Mantenimiento]:
        return self._entidades(
            self._s.scalars(
                select(MantenimientoORM).where(MantenimientoORM.fin.is_(None), MantenimientoORM.inicio < limite)
            )
        )


class SqlAuditoriaRepository:
    def __init__(self, session: Session):
        self._s = session

    def registrar(
        self,
        usuario_id: int | None,
        accion: str,
        entidad: str,
        entidad_id: int | None = None,
        detalle: str | None = None,
    ) -> None:
        self._s.add(
            AuditoriaORM(usuario_id=usuario_id, accion=accion, entidad=entidad, entidad_id=entidad_id, detalle=detalle)
        )

    def listar(self, entidad: str | None, skip: int, limit: int) -> list[RegistroAuditoria]:
        self._s.flush()
        consulta = select(AuditoriaORM).order_by(AuditoriaORM.id.desc())
        if entidad:
            consulta = consulta.where(AuditoriaORM.entidad == entidad)
        return [
            RegistroAuditoria(
                id=a.id,
                usuario_id=a.usuario_id,
                accion=a.accion,
                entidad=a.entidad,
                entidad_id=a.entidad_id,
                detalle=a.detalle,
                fecha=a.fecha,
            )
            for a in self._s.scalars(consulta.offset(skip).limit(limit))
        ]


class SqlUnitOfWork:
    """Una transacción por caso de uso, compartida por todos los repositorios de la sesión."""

    def __init__(self, session: Session):
        self._s = session

    def commit(self) -> None:
        self._s.commit()

    def rollback(self) -> None:
        self._s.rollback()
