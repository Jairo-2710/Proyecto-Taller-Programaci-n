from typing import Protocol

from .entities import ConsultaFuente, EstadoFuente


class FuenteDatosAbiertos(Protocol):
    """Puerto de salida hacia una API pública colombiana (datos.gov.co, DANE...)."""

    nombre: str

    def consultar(self, limite: int) -> ConsultaFuente:
        """Devuelve registros JSON. Lanza FuenteNoDisponibleError si no responde y no hay caché."""

    def estado(self) -> EstadoFuente: ...


class MotorAnalitico(Protocol):
    """Puerto hacia el motor SQL analítico (DuckDB)."""

    def ejecutar(self, tablas: dict[str, list[dict]], sql: str) -> list[dict]:
        """Carga cada lista de registros JSON como una tabla y ejecuta la consulta SQL."""
