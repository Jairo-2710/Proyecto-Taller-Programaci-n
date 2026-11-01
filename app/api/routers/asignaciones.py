from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ...application.asignaciones import AsignacionService
from ...domain.asignaciones.entities import SolicitudEquipos
from ...domain.identidad.entities import Usuario
from ...domain.shared.enums import EstadoAsignacion, Rol
from ..container import get_asignacion_service
from ..deps import requiere_roles, usuario_actual
from ..schemas import (
    AsignacionCrear,
    AsignacionOut,
    EquipoOut,
    SolicitudAsignacion,
    SugerenciaOut,
    normalizar_fecha,
)

router = APIRouter(prefix="/asignaciones", tags=["Asignaciones"])
gestores = requiere_roles(Rol.administrador, Rol.encargado_sala)


def _solicitud(datos: SolicitudAsignacion) -> SolicitudEquipos:
    return SolicitudEquipos(**datos.model_dump())


@router.post("", response_model=AsignacionOut, status_code=201)
def crear_asignacion(
    datos: AsignacionCrear, servicio: AsignacionService = Depends(get_asignacion_service), usuario: Usuario = Depends(gestores)
):
    """Asigna un equipo concreto. Rechaza cruces de horario y equipos no operativos."""
    return servicio.asignar(usuario, datos.equipo_id, datos.actividad, datos.inicio, datos.fin)


@router.post("/sugerencia", response_model=SugerenciaOut)
def sugerir_equipos(
    datos: SolicitudAsignacion, servicio: AsignacionService = Depends(get_asignacion_service), _: Usuario = Depends(gestores)
):
    """Propone los equipos que el sistema elegiría, sin crear asignaciones (el personal decide)."""
    s = servicio.sugerir(_solicitud(datos))
    return SugerenciaOut(
        solicitados=s.solicitados,
        disponibles_compatibles=s.disponibles_compatibles,
        suficientes=s.suficientes,
        equipos_sugeridos=[EquipoOut.model_validate(e) for e in s.equipos],
    )


@router.post("/solicitud", response_model=list[AsignacionOut], status_code=201)
def solicitar_equipos(
    datos: SolicitudAsignacion, servicio: AsignacionService = Depends(get_asignacion_service), usuario: Usuario = Depends(gestores)
):
    """Asigna `cantidad` equipos compatibles. Todo o nada: si no alcanzan, no se asigna ninguno."""
    return servicio.solicitar(usuario, _solicitud(datos))


@router.get("", response_model=list[AsignacionOut])
def listar_asignaciones(
    equipo_id: int | None = None,
    estado: EstadoAsignacion | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    servicio: AsignacionService = Depends(get_asignacion_service),
    _: Usuario = Depends(requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.docente, Rol.coordinador)),
):
    """Historial de asignaciones con filtros opcionales."""
    return servicio.listar(
        equipo_id,
        estado,
        normalizar_fecha(desde) if desde else None,
        normalizar_fecha(hasta) if hasta else None,
        skip,
        limit,
    )


@router.get("/{asignacion_id}", response_model=AsignacionOut)
def obtener_asignacion(
    asignacion_id: int, servicio: AsignacionService = Depends(get_asignacion_service), _: Usuario = Depends(usuario_actual)
):
    return servicio.obtener(asignacion_id)


@router.patch("/{asignacion_id}/cancelar", response_model=AsignacionOut)
def cancelar_asignacion(
    asignacion_id: int, servicio: AsignacionService = Depends(get_asignacion_service), usuario: Usuario = Depends(gestores)
):
    return servicio.cancelar(usuario, asignacion_id)
