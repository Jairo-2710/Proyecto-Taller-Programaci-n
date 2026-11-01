from dataclasses import dataclass, field
from datetime import datetime

from ..shared.enums import EstadoCircuito


@dataclass
class ConsultaFuente:
    """Resultado de consultar una API pública externa."""

    fuente: str
    registros: list[dict]
    consultado_en: datetime
    estado_circuito: EstadoCircuito
    desde_cache: bool = False  # True si la API falló y se devolvió el último dato bueno


@dataclass
class EstadoFuente:
    fuente: str
    descripcion: str
    url: str
    estado_circuito: EstadoCircuito
    fallos_consecutivos: int
    transiciones: list[str] = field(default_factory=list)
