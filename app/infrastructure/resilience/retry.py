"""Reintentos con backoff exponencial y jitter."""
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def calcular_espera(
    intento: int,
    base_s: float = 0.5,
    factor: float = 2.0,
    max_s: float = 8.0,
    jitter: float = 0.0,
    aleatorio: Callable[[], float] = random.random,
) -> float:
    """Espera antes del reintento número `intento` (1, 2, 3...): base · factor^(intento-1), con tope.

    Con base=0.5 y factor=2 → 0.5 s, 1 s, 2 s, 4 s, 8 s...
    El jitter (±fracción) evita que muchos clientes reintenten exactamente al mismo tiempo.
    """
    espera = min(base_s * factor ** (intento - 1), max_s)
    if jitter:
        espera *= 1 + jitter * (2 * aleatorio() - 1)
    return max(espera, 0.0)


def reintentar(
    funcion: Callable[[], T],
    *,
    intentos: int = 3,
    base_s: float = 0.5,
    factor: float = 2.0,
    max_s: float = 8.0,
    jitter: float = 0.1,
    reintentables: tuple[type[BaseException], ...] = (Exception,),
    dormir: Callable[[float], None] = time.sleep,
    aleatorio: Callable[[], float] = random.random,
    al_reintentar: Callable[[int, float, BaseException], None] | None = None,
) -> T:
    """Ejecuta `funcion`; si lanza una excepción reintentable espera (backoff) y vuelve a intentar.

    Las excepciones que no están en `reintentables` se propagan de inmediato (no tiene sentido
    reintentar un error permanente ni un circuito abierto). Tras el último intento se propaga el error.
    """
    for intento in range(1, intentos + 1):
        try:
            return funcion()
        except reintentables as error:
            if intento == intentos:
                raise
            espera = calcular_espera(intento, base_s, factor, max_s, jitter, aleatorio)
            if al_reintentar:
                al_reintentar(intento, espera, error)
            dormir(espera)
    raise RuntimeError("intentos debe ser >= 1")  # pragma: no cover
