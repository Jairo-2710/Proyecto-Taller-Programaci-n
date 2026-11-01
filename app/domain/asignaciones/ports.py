from datetime import datetime
from typing import Protocol

from ..inventario.entities import Equipo
from ..shared.enums import EstadoAsignacion
from .entities import Asignacion, CriteriosDisponibilidad


class AsignacionRepository(Protocol):
    def obtener(self, asignacion_id: int) -> Asignacion | None: ...

    def guardar(self, asignacion: Asignacion) -> Asignacion: ...

    def guardar_varias(self, asignaciones: list[Asignacion]) -> list[Asignacion]: ...

    def listar(
        self,
        equipo_id: int | None,
        estado: EstadoAsignacion | None,
        desde: datetime | None,
        hasta: datetime | None,
        skip: int,
        limit: int,
    ) -> list[Asignacion]: ...

    def ids_en_conflicto(self, equipo_id: int, inicio: datetime, fin: datetime) -> list[int]:
        """Asignaciones activas del equipo que se cruzan con el periodo."""

    def pendientes_futuras(self, equipo_id: int, desde: datetime) -> list[int]:
        """Asignaciones activas del equipo que terminan después de `desde`."""

    def activas_en_rango(self, desde: datetime, hasta: datetime) -> list[Asignacion]: ...

    def contar_en_curso(self, ahora: datetime) -> int: ...

    def equipos_disponibles(self, criterios: CriteriosDisponibilidad) -> list[Equipo]:
        """Equipos operativos, sin asignación ni mantenimiento que se cruce con el periodo,
        ordenados de menor a mayor uso histórico (reparto equilibrado del desgaste)."""
