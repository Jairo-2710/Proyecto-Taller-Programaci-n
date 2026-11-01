from datetime import datetime, timedelta

from fastapi import HTTPException

from ..config import ahora
from .schemas import normalizar_fecha


def rango_por_defecto(desde: datetime | None, hasta: datetime | None) -> tuple[datetime, datetime]:
    """Si no se indica, analiza los últimos 30 días."""
    hasta = normalizar_fecha(hasta) if hasta else ahora()
    desde = normalizar_fecha(desde) if desde else hasta - timedelta(days=30)
    if desde >= hasta:
        raise HTTPException(status_code=422, detail="'desde' debe ser anterior a 'hasta'")
    if (hasta - desde) > timedelta(days=366):
        raise HTTPException(status_code=422, detail="El periodo de análisis no puede superar un año")
    return desde, hasta
