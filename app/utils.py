from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import COL_TZ


def normalizar_fecha(valor: datetime) -> datetime:
    """Las fechas se guardan sin zona horaria, en hora de Colombia (UTC-5).

    Si el cliente envía una fecha con zona horaria se convierte; si no la trae,
    se interpreta como hora local de la sede.
    """
    if valor.tzinfo is not None:
        valor = valor.astimezone(COL_TZ).replace(tzinfo=None)
    return valor


def obtener_o_404(db: Session, modelo, id_: int, mensaje: str):
    objeto = db.get(modelo, id_)
    if objeto is None:
        raise HTTPException(status_code=404, detail=mensaje)
    return objeto
