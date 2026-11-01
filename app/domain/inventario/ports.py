from typing import Protocol

from ..shared.enums import EstadoEquipo, TipoEquipo
from .entities import Equipo, Zona


class ZonaRepository(Protocol):
    def obtener(self, zona_id: int) -> Zona | None: ...

    def por_nombre(self, nombre: str) -> Zona | None: ...

    def listar(self) -> list[Zona]: ...

    def contar(self) -> int: ...

    def guardar(self, zona: Zona) -> Zona: ...


class EquipoRepository(Protocol):
    def obtener(self, equipo_id: int) -> Equipo | None: ...

    def por_codigo(self, codigo: str) -> Equipo | None: ...

    def listar(
        self,
        zona_id: int | None,
        tipo: TipoEquipo | None,
        estado: EstadoEquipo | None,
        activo: bool,
        skip: int,
        limit: int,
    ) -> list[Equipo]: ...

    def listar_activos(self) -> list[Equipo]: ...

    def todos(self) -> list[Equipo]:
        """Todos los equipos, incluidos los desactivados (para reportes históricos)."""

    def guardar(self, equipo: Equipo) -> Equipo: ...
