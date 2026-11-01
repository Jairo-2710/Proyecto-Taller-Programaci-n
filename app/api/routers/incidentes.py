from fastapi import APIRouter, Depends, Query

from ...application.mantenimiento import IncidenteService, MantenimientoService
from ...domain.identidad.entities import Usuario
from ...domain.shared.enums import EstadoIncidente, Rol, Severidad
from ..container import get_incidente_service, get_mantenimiento_service
from ..deps import requiere_roles, usuario_actual
from ..schemas import (
    IncidenteActualizar,
    IncidenteCrear,
    IncidenteOut,
    MantenimientoCerrar,
    MantenimientoCrear,
    MantenimientoOut,
)

router = APIRouter(prefix="/incidentes", tags=["Incidentes y mantenimiento"])
router_mantenimientos = APIRouter(prefix="/mantenimientos", tags=["Incidentes y mantenimiento"])
tecnicos = requiere_roles(Rol.administrador, Rol.soporte)
consulta_roles = requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)


# ---------------------------------------------------------------- incidentes
@router.post("", response_model=IncidenteOut, status_code=201)
def reportar_incidente(
    datos: IncidenteCrear, servicio: IncidenteService = Depends(get_incidente_service), usuario: Usuario = Depends(usuario_actual)
):
    """Cualquier usuario autenticado puede reportar una falla.

    Si la severidad es alta o crítica, el equipo pasa a 'fuera_de_servicio' hasta que se resuelva.
    """
    return servicio.reportar(usuario, datos.equipo_id, datos.descripcion, datos.severidad)


@router.get("", response_model=list[IncidenteOut])
def listar_incidentes(
    equipo_id: int | None = None,
    estado: EstadoIncidente | None = None,
    severidad: Severidad | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    servicio: IncidenteService = Depends(get_incidente_service),
    _: Usuario = Depends(consulta_roles),
):
    return servicio.listar(equipo_id, estado, severidad, skip, limit)


@router.get("/{incidente_id}", response_model=IncidenteOut)
def obtener_incidente(
    incidente_id: int, servicio: IncidenteService = Depends(get_incidente_service), _: Usuario = Depends(consulta_roles)
):
    return servicio.obtener(incidente_id)


@router.patch("/{incidente_id}", response_model=IncidenteOut)
def actualizar_incidente(
    incidente_id: int,
    datos: IncidenteActualizar,
    servicio: IncidenteService = Depends(get_incidente_service),
    usuario: Usuario = Depends(tecnicos),
):
    """Cambia el estado de atención (abierto → en_atencion → resuelto) y registra acciones y responsable."""
    return servicio.actualizar(usuario, incidente_id, datos.estado, datos.responsable_id, datos.acciones)


# ---------------------------------------------------------------- mantenimientos
@router_mantenimientos.post("", response_model=MantenimientoOut, status_code=201)
def iniciar_mantenimiento(
    datos: MantenimientoCrear,
    servicio: MantenimientoService = Depends(get_mantenimiento_service),
    usuario: Usuario = Depends(tecnicos),
):
    """Abre un mantenimiento: el equipo pasa a 'en_mantenimiento' y deja de asignarse."""
    resultado = servicio.iniciar(usuario, datos.equipo_id, datos.tipo, datos.descripcion, datos.incidente_id)
    salida = MantenimientoOut.model_validate(resultado.mantenimiento)
    salida.asignaciones_afectadas = resultado.asignaciones_afectadas
    return salida


@router_mantenimientos.patch("/{mantenimiento_id}/cerrar", response_model=MantenimientoOut)
def cerrar_mantenimiento(
    mantenimiento_id: int,
    datos: MantenimientoCerrar,
    servicio: MantenimientoService = Depends(get_mantenimiento_service),
    usuario: Usuario = Depends(tecnicos),
):
    return servicio.cerrar(usuario, mantenimiento_id, datos.acciones)


@router_mantenimientos.get("", response_model=list[MantenimientoOut])
def listar_mantenimientos(
    equipo_id: int | None = None,
    abiertos: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    servicio: MantenimientoService = Depends(get_mantenimiento_service),
    _: Usuario = Depends(consulta_roles),
):
    return servicio.listar(equipo_id, abiertos, skip, limit)
