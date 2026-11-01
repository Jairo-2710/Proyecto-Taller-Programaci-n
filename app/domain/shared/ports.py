"""Puertos transversales (interfaces que implementa la infraestructura)."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Un reloj es una función sin argumentos. Se inyecta para poder fijar la hora en las pruebas.
Reloj = Callable[[], datetime]


class UnitOfWork(Protocol):
    """Una transacción por caso de uso."""

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


@dataclass
class RegistroAuditoria:
    id: int | None
    usuario_id: int | None
    accion: str
    entidad: str
    entidad_id: int | None
    detalle: str | None
    fecha: datetime | None = None


class AuditoriaRepository(Protocol):
    def registrar(
        self,
        usuario_id: int | None,
        accion: str,
        entidad: str,
        entidad_id: int | None = None,
        detalle: str | None = None,
    ) -> None: ...

    def listar(self, entidad: str | None, skip: int, limit: int) -> list[RegistroAuditoria]: ...
