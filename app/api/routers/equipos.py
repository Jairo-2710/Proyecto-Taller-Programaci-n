from datetime import datetime

from fastapi import APIRouter, Depends, Query

from ...application.asignaciones import AsignacionService
from ...application.inventario import HistorialEquipoService, InventarioService
from ...domain.asignaciones.entities import CriteriosDisponibilidad
from ...domain.identidad.entities import Usuario
from ...domain.inventario.entities import Equipo
from ...domain.shared.enums import EstadoEquipo, Rol, TipoEquipo
from ..container import get_asignacion_service, get_historial_service, get_inventario_service
from ..deps import requiere_roles, usuario_actual
from ..schemas import (
    AsignacionOut,
    EquipoActualizar,
    EquipoCrear,
    EquipoOut,
    HistorialEquipoOut,
    IncidenteOut,
    MantenimientoOut,
    ZonaCrear,
    ZonaOut,
    normalizar_fecha,
)

router = APIRouter(prefix="/equipos", tags=["Inventario"])
router_zonas = APIRouter(prefix="/zonas", tags=["Inventario"])
solo_admin = requiere_roles(Rol.administrador)


# ---------------------------------------------------------------- zonas
@router_zonas.get("", response_model=list[ZonaOut])
def listar_zonas(servicio: InventarioService = Depends(get_inventario_service), _: Usuario = Depends(usuario_actual)):
    return servicio.listar_zonas()


@router_zonas.post("", response_model=ZonaOut, status_code=201)
def crear_zona(
    datos: ZonaCrear, servicio: InventarioService = Depends(get_inventario_service), admin: Usuario = Depends(solo_admin)
):
    return servicio.crear_zona(admin, datos.nombre, datos.descripcion)


# ---------------------------------------------------------------- equipos
@router.post("", response_model=EquipoOut, status_code=201)
def crear_equipo(
    datos: EquipoCrear, servicio: InventarioService = Depends(get_inventario_service), admin: Usuario = Depends(solo_admin)
):
    return servicio.crear_equipo(admin, Equipo(**datos.model_dump()))


@router.get("", response_model=list[EquipoOut])
def listar_equipos(
    zona_id: int | None = None,
    tipo: TipoEquipo | None = None,
    estado: EstadoEquipo | None = None,
    activo: bool = True,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    servicio: InventarioService = Depends(get_inventario_service),
    _: Usuario = Depends(usuario_actual),
):
    """Consulta el inventario por zona, tipo y estado."""
    return servicio.listar_equipos(zona_id, tipo, estado, activo, skip, limit)


@router.get("/disponibles", response_model=list[EquipoOut])
def equipos_disponibles(
    inicio: datetime,
    fin: datetime,
    zona_id: int | None = None,
    tipo: TipoEquipo | None = None,
    ram_min: int | None = Query(None, gt=0),
    almacenamiento_min: int | None = Query(None, gt=0),
    software: list[str] | None = Query(None, description="Software requerido (puede repetirse)"),
    servicio: AsignacionService = Depends(get_asignacion_service),
    _: Usuario = Depends(usuario_actual),
):
    """Equipos operativos y libres durante el periodo, ordenados para repartir el uso."""
    return servicio.disponibles(
        CriteriosDisponibilidad(
            inicio=normalizar_fecha(inicio),
            fin=normalizar_fecha(fin),
            zona_id=zona_id,
            tipo=tipo,
            ram_min=ram_min,
            almacenamiento_min=almacenamiento_min,
            software=software or [],
        )
    )


@router.get("/{equipo_id}", response_model=EquipoOut)
def obtener_equipo(
    equipo_id: int, servicio: InventarioService = Depends(get_inventario_service), _: Usuario = Depends(usuario_actual)
):
    return servicio.obtener_equipo(equipo_id)


@router.patch("/{equipo_id}", response_model=EquipoOut)
def actualizar_equipo(
    equipo_id: int,
    datos: EquipoActualizar,
    servicio: InventarioService = Depends(get_inventario_service),
    admin: Usuario = Depends(solo_admin),
):
    return servicio.actualizar_equipo(admin, equipo_id, datos.model_dump(exclude_unset=True))


@router.delete("/{equipo_id}", response_model=EquipoOut)
def desactivar_equipo(
    equipo_id: int, servicio: InventarioService = Depends(get_inventario_service), admin: Usuario = Depends(solo_admin)
):
    """Baja lógica: el equipo se conserva con su historial pero deja de asignarse."""
    return servicio.desactivar_equipo(admin, equipo_id)


@router.get("/{equipo_id}/historial", response_model=HistorialEquipoOut)
def historial_equipo(
    equipo_id: int,
    servicio: HistorialEquipoService = Depends(get_historial_service),
    _: Usuario = Depends(requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)),
):
    """Trazabilidad completa del equipo: asignaciones, incidentes y mantenimientos."""
    h = servicio.obtener(equipo_id)
    return HistorialEquipoOut(
        equipo=EquipoOut.model_validate(h.equipo),
        asignaciones=[AsignacionOut.model_validate(a) for a in h.asignaciones],
        incidentes=[IncidenteOut.model_validate(i) for i in h.incidentes],
        mantenimientos=[MantenimientoOut.model_validate(m) for m in h.mantenimientos],
    )
