from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import ahora
from ..enums import EstadoEquipo, EstadoIncidente, Severidad
from ..models import Equipo, Incidente, Mantenimiento

SEVERIDADES_BLOQUEANTES = (Severidad.alta, Severidad.critica)


def recalcular_estado(db: Session, equipo: Equipo) -> EstadoEquipo:
    """Deriva el estado operativo del equipo a partir de sus mantenimientos e incidentes.

    - Mantenimiento abierto            -> en_mantenimiento
    - Incidente grave/crítico sin cerrar -> fuera_de_servicio
    - En otro caso                      -> disponible
    """
    db.flush()  # la sesión no hace autoflush: asegura que los cambios recientes se vean
    mantenimientos_abiertos = db.scalar(
        select(func.count())
        .select_from(Mantenimiento)
        .where(Mantenimiento.equipo_id == equipo.id, Mantenimiento.fin.is_(None))
    )
    incidentes_graves = db.scalar(
        select(func.count())
        .select_from(Incidente)
        .where(
            Incidente.equipo_id == equipo.id,
            Incidente.estado != EstadoIncidente.resuelto,
            Incidente.severidad.in_(SEVERIDADES_BLOQUEANTES),
        )
    )
    if mantenimientos_abiertos:
        nuevo = EstadoEquipo.en_mantenimiento
    elif incidentes_graves:
        nuevo = EstadoEquipo.fuera_de_servicio
    else:
        nuevo = EstadoEquipo.disponible
    if equipo.estado != nuevo:
        equipo.estado = nuevo
        equipo.actualizado_en = ahora()
    return nuevo
