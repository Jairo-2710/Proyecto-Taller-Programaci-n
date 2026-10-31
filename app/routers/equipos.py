from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ahora
from ..database import get_db
from ..deps import requiere_roles, usuario_actual
from ..enums import EstadoAsignacion, EstadoEquipo, Rol, TipoEquipo
from ..errors import ReglaNegocioError
from ..models import Asignacion, Equipo, Incidente, Mantenimiento, Usuario, Zona
from ..schemas import (
    AsignacionOut,
    EquipoActualizar,
    EquipoCrear,
    EquipoOut,
    HistorialEquipoOut,
    IncidenteOut,
    MantenimientoOut,
)
from ..services import asignaciones as svc_asignaciones
from ..services import auditoria
from ..utils import normalizar_fecha, obtener_o_404

router = APIRouter(prefix="/equipos", tags=["Inventario"])
solo_admin = requiere_roles(Rol.administrador)


@router.post("", response_model=EquipoOut, status_code=201)
def crear_equipo(datos: EquipoCrear, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    codigo = datos.codigo.upper()
    if db.scalar(select(Equipo).where(Equipo.codigo == codigo)):
        raise ReglaNegocioError(f"Ya existe un equipo con el código {codigo}")
    obtener_o_404(db, Zona, datos.zona_id, "Zona no encontrada")
    equipo = Equipo(**datos.model_dump(exclude={"codigo"}), codigo=codigo)
    db.add(equipo)
    db.flush()
    auditoria.registrar(db, admin, "crear", "equipo", equipo.id, codigo)
    db.commit()
    return equipo


@router.get("", response_model=list[EquipoOut])
def listar_equipos(
    zona_id: int | None = None,
    tipo: TipoEquipo | None = None,
    estado: EstadoEquipo | None = None,
    activo: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
):
    """Consulta el inventario por zona, tipo y estado."""
    consulta = select(Equipo).where(Equipo.activo.is_(activo)).order_by(Equipo.codigo)
    if zona_id is not None:
        consulta = consulta.where(Equipo.zona_id == zona_id)
    if tipo is not None:
        consulta = consulta.where(Equipo.tipo == tipo)
    if estado is not None:
        consulta = consulta.where(Equipo.estado == estado)
    return list(db.scalars(consulta.offset(skip).limit(limit)).unique())


@router.get("/disponibles", response_model=list[EquipoOut])
def equipos_disponibles(
    inicio: datetime,
    fin: datetime,
    zona_id: int | None = None,
    tipo: TipoEquipo | None = None,
    ram_min: int | None = Query(None, gt=0),
    almacenamiento_min: int | None = Query(None, gt=0),
    software: list[str] | None = Query(None, description="Software requerido (puede repetirse)"),
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_actual),
):
    """Equipos operativos y libres durante el periodo, ordenados para repartir el uso."""
    inicio, fin = normalizar_fecha(inicio), normalizar_fecha(fin)
    if fin <= inicio:
        raise HTTPException(status_code=422, detail="'fin' debe ser posterior a 'inicio'")
    return svc_asignaciones.equipos_disponibles(
        db,
        inicio,
        fin,
        zona_id=zona_id,
        tipo=tipo,
        ram_min=ram_min,
        almacenamiento_min=almacenamiento_min,
        software=software,
    )


@router.get("/{equipo_id}", response_model=EquipoOut)
def obtener_equipo(equipo_id: int, db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    return obtener_o_404(db, Equipo, equipo_id, "Equipo no encontrado")


@router.patch("/{equipo_id}", response_model=EquipoOut)
def actualizar_equipo(
    equipo_id: int,
    datos: EquipoActualizar,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(solo_admin),
):
    equipo = obtener_o_404(db, Equipo, equipo_id, "Equipo no encontrado")
    cambios = datos.model_dump(exclude_unset=True)
    if "zona_id" in cambios and cambios["zona_id"] is not None:
        obtener_o_404(db, Zona, cambios["zona_id"], "Zona no encontrada")
    for campo, valor in cambios.items():
        if valor is not None:
            setattr(equipo, campo, valor)
    equipo.actualizado_en = ahora()
    auditoria.registrar(db, admin, "actualizar", "equipo", equipo.id, ", ".join(cambios))
    db.commit()
    return equipo


@router.delete("/{equipo_id}", response_model=EquipoOut)
def desactivar_equipo(equipo_id: int, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    """Baja lógica: el equipo se conserva con su historial pero deja de asignarse."""
    equipo = obtener_o_404(db, Equipo, equipo_id, "Equipo no encontrado")
    pendientes = list(
        db.scalars(
            select(Asignacion.id).where(
                Asignacion.equipo_id == equipo.id,
                Asignacion.estado == EstadoAsignacion.activa,
                Asignacion.fin > ahora(),
            )
        )
    )
    if pendientes:
        raise ReglaNegocioError(
            "El equipo tiene asignaciones activas pendientes; cancélelas antes de desactivarlo",
            info={"asignaciones_pendientes": pendientes},
        )
    equipo.activo = False
    equipo.actualizado_en = ahora()
    auditoria.registrar(db, admin, "desactivar", "equipo", equipo.id, equipo.codigo)
    db.commit()
    return equipo


@router.get("/{equipo_id}/historial", response_model=HistorialEquipoOut)
def historial_equipo(
    equipo_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)),
):
    """Trazabilidad completa del equipo: asignaciones, incidentes y mantenimientos."""
    equipo = obtener_o_404(db, Equipo, equipo_id, "Equipo no encontrado")
    return HistorialEquipoOut(
        equipo=EquipoOut.model_validate(equipo),
        asignaciones=[
            AsignacionOut.model_validate(a)
            for a in db.scalars(select(Asignacion).where(Asignacion.equipo_id == equipo_id).order_by(Asignacion.inicio))
        ],
        incidentes=[
            IncidenteOut.model_validate(i)
            for i in db.scalars(
                select(Incidente).where(Incidente.equipo_id == equipo_id).order_by(Incidente.fecha_reporte)
            )
        ],
        mantenimientos=[
            MantenimientoOut.model_validate(m)
            for m in db.scalars(
                select(Mantenimiento).where(Mantenimiento.equipo_id == equipo_id).order_by(Mantenimiento.inicio)
            )
        ],
    )
