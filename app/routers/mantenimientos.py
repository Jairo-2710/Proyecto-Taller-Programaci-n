from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ahora
from ..database import get_db
from ..deps import requiere_roles
from ..enums import EstadoAsignacion, Rol
from ..errors import ReglaNegocioError
from ..models import Asignacion, Equipo, Incidente, Mantenimiento, Usuario
from ..schemas import MantenimientoCerrar, MantenimientoCrear, MantenimientoOut
from ..services import auditoria
from ..services.equipos import recalcular_estado
from ..utils import obtener_o_404

router = APIRouter(prefix="/mantenimientos", tags=["Incidentes y mantenimiento"])
tecnicos = requiere_roles(Rol.administrador, Rol.soporte)
consulta_roles = requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)


@router.post("", response_model=MantenimientoOut, status_code=201)
def iniciar_mantenimiento(datos: MantenimientoCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(tecnicos)):
    """Abre un mantenimiento: el equipo pasa a 'en_mantenimiento' y deja de asignarse."""
    equipo = obtener_o_404(db, Equipo, datos.equipo_id, "Equipo no encontrado")
    if not equipo.activo:
        raise ReglaNegocioError("El equipo está desactivado")
    if db.scalar(select(Mantenimiento.id).where(Mantenimiento.equipo_id == equipo.id, Mantenimiento.fin.is_(None))):
        raise ReglaNegocioError(f"El equipo {equipo.codigo} ya tiene un mantenimiento abierto")
    if datos.incidente_id is not None:
        incidente = obtener_o_404(db, Incidente, datos.incidente_id, "Incidente no encontrado")
        if incidente.equipo_id != equipo.id:
            raise ReglaNegocioError("El incidente pertenece a otro equipo")

    mantenimiento = Mantenimiento(
        equipo_id=equipo.id,
        incidente_id=datos.incidente_id,
        tipo=datos.tipo,
        descripcion=datos.descripcion,
        responsable_id=usuario.id,
        inicio=ahora(),
    )
    db.add(mantenimiento)
    db.flush()
    recalcular_estado(db, equipo)
    afectadas = list(
        db.scalars(
            select(Asignacion.id).where(
                Asignacion.equipo_id == equipo.id,
                Asignacion.estado == EstadoAsignacion.activa,
                Asignacion.fin > ahora(),
            )
        )
    )
    auditoria.registrar(db, usuario, "iniciar", "mantenimiento", mantenimiento.id, f"equipo={equipo.codigo}")
    db.commit()
    salida = MantenimientoOut.model_validate(mantenimiento)
    salida.asignaciones_afectadas = afectadas
    return salida


@router.patch("/{mantenimiento_id}/cerrar", response_model=MantenimientoOut)
def cerrar_mantenimiento(
    mantenimiento_id: int,
    datos: MantenimientoCerrar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(tecnicos),
):
    mantenimiento = obtener_o_404(db, Mantenimiento, mantenimiento_id, "Mantenimiento no encontrado")
    if mantenimiento.fin is not None:
        raise ReglaNegocioError("El mantenimiento ya estaba cerrado")
    mantenimiento.fin = ahora()
    mantenimiento.acciones = datos.acciones
    equipo = db.get(Equipo, mantenimiento.equipo_id)
    recalcular_estado(db, equipo)
    auditoria.registrar(db, usuario, "cerrar", "mantenimiento", mantenimiento.id, f"equipo={equipo.codigo}")
    db.commit()
    return mantenimiento


@router.get("", response_model=list[MantenimientoOut])
def listar_mantenimientos(
    equipo_id: int | None = None,
    abiertos: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Usuario = Depends(consulta_roles),
):
    consulta = select(Mantenimiento).order_by(Mantenimiento.inicio.desc())
    if equipo_id is not None:
        consulta = consulta.where(Mantenimiento.equipo_id == equipo_id)
    if abiertos is True:
        consulta = consulta.where(Mantenimiento.fin.is_(None))
    elif abiertos is False:
        consulta = consulta.where(Mantenimiento.fin.is_not(None))
    return db.scalars(consulta.offset(skip).limit(limit)).all()
