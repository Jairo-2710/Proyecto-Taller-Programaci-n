from datetime import datetime

from fastapi import APIRouter, Depends

from ...application.analisis import AnalisisService
from ...application.analitica import DatosAbiertosService, EstadisticasService
from ...domain.identidad.entities import Usuario
from ...domain.shared.enums import Rol
from ..container import get_analisis_service, get_datos_abiertos_service, get_estadisticas_service
from ..deps import requiere_roles
from ..rangos import rango_por_defecto
from ..schemas import (
    AnalisisDatosAbiertosOut,
    DemandaOut,
    EstadisticasAsignacionesOut,
    EstadisticasEquiposOut,
    EstadoFuenteOut,
    IncidentesEquipoOut,
    RecomendacionesOut,
    ResultadoFuenteOut,
    ResumenOut,
    UtilizacionEquipoOut,
)

router = APIRouter(prefix="/analisis", tags=["Análisis y optimización"])
router_analitica = APIRouter(prefix="/analitica", tags=["Analítica con DuckDB"])
router_datos_abiertos = APIRouter(prefix="/datos-abiertos", tags=["APIs públicas colombianas"])
acceso = requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)


# ---------------------------------------------------------------- reglas de decisión
@router.get("/resumen", response_model=ResumenOut)
def resumen_general(servicio: AnalisisService = Depends(get_analisis_service), _: Usuario = Depends(acceso)):
    """Estado actual del inventario, asignaciones en curso e incidentes abiertos."""
    return servicio.resumen()


@router.get("/utilizacion", response_model=list[UtilizacionEquipoOut])
def utilizacion(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    zona_id: int | None = None,
    servicio: AnalisisService = Depends(get_analisis_service),
    _: Usuario = Depends(acceso),
):
    """Indicador de utilización por equipo (alta / normal / baja)."""
    desde, hasta = rango_por_defecto(desde, hasta)
    return servicio.utilizacion_por_equipo(desde, hasta, zona_id)


@router.get("/demanda", response_model=DemandaOut)
def demanda(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    servicio: AnalisisService = Depends(get_analisis_service),
    _: Usuario = Depends(acceso),
):
    """Demanda por zona, día de la semana y hora del día."""
    desde, hasta = rango_por_defecto(desde, hasta)
    return servicio.demanda_por_zona(desde, hasta)


@router.get("/incidentes", response_model=list[IncidentesEquipoOut])
def incidentes(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    servicio: AnalisisService = Depends(get_analisis_service),
    _: Usuario = Depends(acceso),
):
    """Equipos con más incidentes y tiempo medio de resolución."""
    desde, hasta = rango_por_defecto(desde, hasta)
    return servicio.incidentes_por_equipo(desde, hasta)


@router.get("/recomendaciones", response_model=RecomendacionesOut)
def recomendaciones(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    servicio: AnalisisService = Depends(get_analisis_service),
    _: Usuario = Depends(acceso),
):
    """Recomendaciones basadas en reglas de decisión y datos históricos."""
    desde, hasta = rango_por_defecto(desde, hasta)
    return servicio.recomendaciones(desde, hasta)


# ---------------------------------------------------------------- estadísticas con DuckDB
@router_analitica.get("/equipos", response_model=EstadisticasEquiposOut)
def estadisticas_equipos(servicio: EstadisticasService = Depends(get_estadisticas_service), _: Usuario = Depends(acceso)):
    """Query SQL (DuckDB): estadísticas descriptivas de los equipos por zona y tipo."""
    return servicio.equipos()


@router_analitica.get("/asignaciones", response_model=EstadisticasAsignacionesOut)
def estadisticas_asignaciones(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    servicio: EstadisticasService = Depends(get_estadisticas_service),
    _: Usuario = Depends(acceso),
):
    """Queries SQL (DuckDB): duración de las asignaciones por zona (media, mediana, p90) y horas pico."""
    desde, hasta = rango_por_defecto(desde, hasta)
    return servicio.asignaciones(desde, hasta)


# ---------------------------------------------------------------- APIs públicas colombianas
def _a_estado_out(e) -> EstadoFuenteOut:
    return EstadoFuenteOut(
        fuente=e.fuente,
        descripcion=e.descripcion,
        url=e.url,
        estado_circuito=e.estado_circuito.value,
        estado_circuito_en=e.estado_circuito.ingles,
        fallos_consecutivos=e.fallos_consecutivos,
        transiciones=e.transiciones,
    )


@router_datos_abiertos.get("/estado", response_model=list[EstadoFuenteOut])
def estado_fuentes(servicio: DatosAbiertosService = Depends(get_datos_abiertos_service), _: Usuario = Depends(acceso)):
    """Estado del circuit breaker de cada API pública (CLOSED / OPEN / HALF_OPEN)."""
    return [_a_estado_out(e) for e in servicio.estados()]


@router_datos_abiertos.get("/analisis", response_model=AnalisisDatosAbiertosOut)
def analisis_datos_abiertos(
    servicio: DatosAbiertosService = Depends(get_datos_abiertos_service), _: Usuario = Depends(acceso)
):
    """Consulta datos.gov.co y DANE (con retry y circuit breaker) y los analiza con SQL en DuckDB."""
    a = servicio.analizar()
    return AnalisisDatosAbiertosOut(
        fuentes=[
            ResultadoFuenteOut(
                fuente=f.fuente,
                estado_circuito=f.estado_circuito.value,
                estado_circuito_en=f.estado_circuito.ingles,
                registros=f.registros,
                desde_cache=f.desde_cache,
                error=f.error,
            )
            for f in a.fuentes
        ],
        ranking_departamentos=a.ranking_departamentos,
        estadisticas_departamentos=a.estadisticas_departamentos,
        advertencias=a.advertencias,
    )
