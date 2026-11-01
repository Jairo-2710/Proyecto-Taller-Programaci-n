from dataclasses import dataclass, field
from datetime import datetime

from ..shared.enums import EstadoAsignacion, TipoEquipo


@dataclass
class Asignacion:
    equipo_id: int
    usuario_id: int
    actividad: str
    inicio: datetime
    fin: datetime
    estado: EstadoAsignacion = EstadoAsignacion.activa
    grupo: str | None = None  # une las asignaciones creadas por una misma solicitud
    creado_en: datetime | None = None
    cancelada_en: datetime | None = None
    id: int | None = None


@dataclass
class CriteriosDisponibilidad:
    inicio: datetime
    fin: datetime
    zona_id: int | None = None
    tipo: TipoEquipo | None = None
    ram_min: int | None = None
    almacenamiento_min: int | None = None
    software: list[str] = field(default_factory=list)


@dataclass
class SolicitudEquipos:
    """Pide `cantidad` equipos para una actividad; el sistema elige los más adecuados."""

    actividad: str
    inicio: datetime
    fin: datetime
    cantidad: int
    zona_id: int | None = None
    tipo: TipoEquipo | None = None
    ram_min: int | None = None
    almacenamiento_min: int | None = None
    software: list[str] = field(default_factory=list)
    permitir_otras_zonas: bool = False

    def criterios(self, zona_id: int | None) -> CriteriosDisponibilidad:
        return CriteriosDisponibilidad(
            inicio=self.inicio,
            fin=self.fin,
            zona_id=zona_id,
            tipo=self.tipo,
            ram_min=self.ram_min,
            almacenamiento_min=self.almacenamiento_min,
            software=self.software,
        )


@dataclass
class Sugerencia:
    solicitados: int
    disponibles_compatibles: int
    equipos: list = field(default_factory=list)

    @property
    def suficientes(self) -> bool:
        return len(self.equipos) >= self.solicitados
