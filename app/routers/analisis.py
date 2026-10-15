from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import ahora
from ..database import get_db
from ..deps import requiere_roles
from ..enums import Rol
from ..models import Usuario
from ..schemas import (
    DemandaOut,
    IncidentesEquipoOut,
    RecomendacionesOut,
    ResumenOut,
    UtilizacionEquipoOut,
)
from ..services import analisis
from ..utils import normalizar_fecha

router = APIRouter(prefix="/analisis", tags=["Análisis y optimización"])
acceso = requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)


def _rango(desde: datetime | None, hasta: datetime | None) -> tuple[datetime, datetime]:
    """Por defecto analiza los últimos 30 días."""
    hasta = normalizar_fecha(hasta) if hasta else ahora()
    desde = normalizar_fecha(desde) if desde else hasta - timedelta(days=30)
    if desde >= hasta:
        raise HTTPException(status_code=422, detail="'desde' debe ser anterior a 'hasta'")
    if (hasta - desde) > timedelta(days=366):
        raise HTTPException(status_code=422, detail="El periodo de análisis no puede superar un año")
    return desde, hasta


@router.get("/resumen", response_model=ResumenOut)
def resumen_general(db: Session = Depends(get_db), _: Usuario = Depends(acceso)):
    """Estado actual del inventario, asignaciones en curso e incidentes abiertos."""
    return analisis.resumen(db)


@router.get("/utilizacion", response_model=list[UtilizacionEquipoOut])
def utilizacion(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    zona_id: int | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(acceso),
):
    """Indicador de utilización por equipo (alta / normal / baja)."""
    desde, hasta = _rango(desde, hasta)
    return analisis.utilizacion_por_equipo(db, desde, hasta, zona_id)


@router.get("/demanda", response_model=DemandaOut)
def demanda(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(acceso),
):
    """Demanda por zona, día de la semana y hora del día."""
    desde, hasta = _rango(desde, hasta)
    return analisis.demanda_por_zona(db, desde, hasta)


@router.get("/incidentes", response_model=list[IncidentesEquipoOut])
def incidentes(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(acceso),
):
    """Equipos con más incidentes y tiempo medio de resolución."""
    desde, hasta = _rango(desde, hasta)
    return analisis.incidentes_por_equipo(db, desde, hasta)


@router.get("/recomendaciones", response_model=RecomendacionesOut)
def recomendaciones(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(acceso),
):
    """Recomendaciones basadas en reglas de decisión y datos históricos."""
    desde, hasta = _rango(desde, hasta)
    return analisis.recomendaciones(db, desde, hasta)
