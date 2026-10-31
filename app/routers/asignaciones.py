from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ahora
from ..database import get_db
from ..deps import requiere_roles, usuario_actual
from ..enums import EstadoAsignacion, Rol
from ..errors import ReglaNegocioError
from ..models import Asignacion, Usuario
from ..schemas import AsignacionCrear, AsignacionOut, SolicitudAsignacion, SugerenciaOut
from ..services import asignaciones as svc
from ..services import auditoria
from ..models import Equipo
from ..schemas import EquipoOut
from ..utils import normalizar_fecha, obtener_o_404

router = APIRouter(prefix="/asignaciones", tags=["Asignaciones"])
gestores = requiere_roles(Rol.administrador, Rol.encargado_sala)


@router.post("", response_model=AsignacionOut, status_code=201)
def crear_asignacion(datos: AsignacionCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(gestores)):
    """Asigna un equipo concreto. Rechaza cruces de horario y equipos no operativos."""
    equipo = obtener_o_404(db, Equipo, datos.equipo_id, "Equipo no encontrado")
    asignacion = svc.crear_asignacion(db, usuario, datos, equipo)
    db.commit()
    return asignacion


@router.post("/sugerencia", response_model=SugerenciaOut)
def sugerir_equipos(datos: SolicitudAsignacion, db: Session = Depends(get_db), _: Usuario = Depends(gestores)):
    """Propone los equipos que el sistema elegiría, sin crear asignaciones (el personal decide)."""
    elegidos, total = svc.seleccionar_equipos(db, datos)
    return SugerenciaOut(
        solicitados=datos.cantidad,
        disponibles_compatibles=total,
        suficientes=len(elegidos) >= datos.cantidad,
        equipos_sugeridos=[EquipoOut.model_validate(e) for e in elegidos],
    )


@router.post("/solicitud", response_model=list[AsignacionOut], status_code=201)
def solicitar_equipos(datos: SolicitudAsignacion, db: Session = Depends(get_db), usuario: Usuario = Depends(gestores)):
    """Asigna `cantidad` equipos compatibles. Todo o nada: si no alcanzan, no se asigna ninguno."""
    asignaciones = svc.crear_solicitud(db, usuario, datos)
    db.commit()
    return asignaciones


@router.get("", response_model=list[AsignacionOut])
def listar_asignaciones(
    equipo_id: int | None = None,
    estado: EstadoAsignacion | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.docente, Rol.coordinador)),
):
    """Historial de asignaciones con filtros opcionales."""
    consulta = select(Asignacion).order_by(Asignacion.inicio.desc())
    if equipo_id is not None:
        consulta = consulta.where(Asignacion.equipo_id == equipo_id)
    if estado is not None:
        consulta = consulta.where(Asignacion.estado == estado)
    if desde is not None:
        consulta = consulta.where(Asignacion.fin > normalizar_fecha(desde))
    if hasta is not None:
        consulta = consulta.where(Asignacion.inicio < normalizar_fecha(hasta))
    return db.scalars(consulta.offset(skip).limit(limit)).all()


@router.get("/{asignacion_id}", response_model=AsignacionOut)
def obtener_asignacion(asignacion_id: int, db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    return obtener_o_404(db, Asignacion, asignacion_id, "Asignación no encontrada")


@router.patch("/{asignacion_id}/cancelar", response_model=AsignacionOut)
def cancelar_asignacion(asignacion_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(gestores)):
    asignacion = obtener_o_404(db, Asignacion, asignacion_id, "Asignación no encontrada")
    if asignacion.estado == EstadoAsignacion.cancelada:
        raise ReglaNegocioError("La asignación ya estaba cancelada")
    if asignacion.fin <= ahora():
        raise ReglaNegocioError("No se puede cancelar una asignación que ya terminó")
    asignacion.estado = EstadoAsignacion.cancelada
    asignacion.cancelada_en = ahora()
    auditoria.registrar(db, usuario, "cancelar", "asignacion", asignacion.id)
    db.commit()
    return asignacion
