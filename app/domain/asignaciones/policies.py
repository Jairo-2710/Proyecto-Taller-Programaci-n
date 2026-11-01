"""Reglas de negocio puras de asignación (sin base de datos ni HTTP)."""
from datetime import datetime

from ..inventario.entities import Equipo
from ..shared.enums import EstadoEquipo
from ..shared.errors import ReglaNegocioError, ValidacionError


def validar_periodo(inicio: datetime, fin: datetime, max_horas: float) -> None:
    if fin <= inicio:
        raise ValidacionError("'fin' debe ser posterior a 'inicio'")
    horas = (fin - inicio).total_seconds() / 3600
    if horas > max_horas:
        raise ValidacionError(f"Una asignación no puede superar {max_horas:g} horas")


def periodos_se_cruzan(ini_a: datetime, fin_a: datetime, ini_b: datetime, fin_b: datetime) -> bool:
    """Dos periodos se cruzan si cada uno empieza antes de que termine el otro.

    Periodos contiguos (uno termina justo cuando empieza el otro) NO se cruzan.
    """
    return ini_a < fin_b and fin_a > ini_b


def verificar_asignable(
    equipo: Equipo,
    asignaciones_en_conflicto: list[int],
    tiene_mantenimiento_cruzado: bool,
) -> None:
    """Lanza ReglaNegocioError si el equipo no puede asignarse en el periodo."""
    if not equipo.activo:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} está desactivado")
    if equipo.estado == EstadoEquipo.fuera_de_servicio:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} está fuera de servicio")
    if equipo.estado == EstadoEquipo.en_mantenimiento:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} está en mantenimiento")
    if asignaciones_en_conflicto:
        raise ReglaNegocioError(
            f"El equipo {equipo.codigo} ya tiene una asignación que se cruza con el periodo solicitado",
            info={"asignaciones_en_conflicto": asignaciones_en_conflicto},
        )
    if tiene_mantenimiento_cruzado:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} tiene un mantenimiento que se cruza con el periodo")
