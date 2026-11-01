from dataclasses import dataclass, field
from datetime import datetime

from ..shared.enums import EstadoIncidente, Severidad, TipoMantenimiento


@dataclass
class Incidente:
    equipo_id: int
    reportado_por_id: int
    descripcion: str
    severidad: Severidad
    estado: EstadoIncidente = EstadoIncidente.abierto
    responsable_id: int | None = None
    acciones: str | None = None
    fecha_reporte: datetime | None = None
    fecha_cierre: datetime | None = None
    id: int | None = None


@dataclass
class Mantenimiento:
    equipo_id: int
    tipo: TipoMantenimiento
    descripcion: str
    responsable_id: int
    inicio: datetime | None = None
    fin: datetime | None = None  # None = mantenimiento abierto
    incidente_id: int | None = None
    acciones: str | None = None
    id: int | None = None


@dataclass
class ResultadoMantenimiento:
    mantenimiento: Mantenimiento
    asignaciones_afectadas: list[int] = field(default_factory=list)
