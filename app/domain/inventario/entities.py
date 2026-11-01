from dataclasses import dataclass, field
from datetime import datetime

from ..shared.enums import EstadoEquipo, TipoEquipo


@dataclass
class Zona:
    nombre: str
    descripcion: str | None = None
    id: int | None = None


@dataclass
class Equipo:
    codigo: str
    tipo: TipoEquipo
    zona_id: int
    ram_gb: int
    almacenamiento_gb: int
    marca: str | None = None
    procesador: str | None = None
    software: list[str] = field(default_factory=list)
    estado: EstadoEquipo = EstadoEquipo.disponible
    activo: bool = True
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None
    id: int | None = None
