"""Circuit breaker de tres estados.

    CERRADO (CLOSED) ──[N fallos seguidos]──▶ ABIERTO (OPEN)
        ▲                                         │
        │                                  [pasa el tiempo de recuperación]
        │                                         ▼
        └────[la llamada de prueba funciona]── SEMIABIERTO (HALF_OPEN)
                                                  │
              [la llamada de prueba falla] ───────┴──▶ ABIERTO

En estado ABIERTO las llamadas se rechazan al instante, sin tocar la API caída. En SEMIABIERTO se
deja pasar una sola llamada de prueba a la vez.
"""
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TypeVar

from ...domain.shared.enums import EstadoCircuito

T = TypeVar("T")


class CircuitoAbiertoError(Exception):
    """El circuito está abierto: la llamada ni siquiera se intentó."""


class CircuitBreaker:
    def __init__(
        self,
        nombre: str,
        umbral_fallos: int = 3,
        tiempo_recuperacion_s: float = 30.0,
        exitos_para_cerrar: int = 1,
        reloj: Callable[[], float] = time.monotonic,
        excepciones_que_cuentan: tuple[type[BaseException], ...] = (Exception,),
    ):
        self.nombre = nombre
        self._umbral = umbral_fallos
        self._recuperacion = tiempo_recuperacion_s
        self._exitos_para_cerrar = exitos_para_cerrar
        self._reloj = reloj
        self._cuentan = excepciones_que_cuentan
        self._lock = threading.RLock()
        self._estado = EstadoCircuito.cerrado
        self._fallos = 0
        self._exitos_semiabierto = 0
        self._abierto_desde = 0.0
        self._probando = False
        self.transiciones: deque[str] = deque(maxlen=20)

    # ------------------------------------------------------------------ consulta
    @property
    def estado(self) -> EstadoCircuito:
        with self._lock:
            self._avanzar_tiempo()
            return self._estado

    @property
    def fallos_consecutivos(self) -> int:
        with self._lock:
            return self._fallos

    # ------------------------------------------------------------------ uso
    def ejecutar(self, funcion: Callable[[], T]) -> T:
        with self._lock:
            self._avanzar_tiempo()
            if self._estado == EstadoCircuito.abierto:
                restante = max(self._recuperacion - (self._reloj() - self._abierto_desde), 0)
                raise CircuitoAbiertoError(
                    f"Circuito '{self.nombre}' abierto; se probará de nuevo en {restante:.0f} s"
                )
            if self._estado == EstadoCircuito.semiabierto:
                if self._probando:
                    raise CircuitoAbiertoError(f"Circuito '{self.nombre}' semiabierto: ya hay una llamada de prueba")
                self._probando = True
        try:
            resultado = funcion()
        except self._cuentan:
            self._registrar_fallo()
            raise
        except BaseException:
            # Error que no refleja la salud de la API (p. ej. un 404): no cuenta, pero libera la prueba.
            with self._lock:
                self._probando = False
            raise
        self._registrar_exito()
        return resultado

    def reiniciar(self) -> None:
        with self._lock:
            self._transicion(EstadoCircuito.cerrado, "reinicio manual")

    # ------------------------------------------------------------------ internos
    def _avanzar_tiempo(self) -> None:
        if self._estado == EstadoCircuito.abierto and self._reloj() - self._abierto_desde >= self._recuperacion:
            self._transicion(EstadoCircuito.semiabierto, "terminó el tiempo de recuperación")

    def _registrar_fallo(self) -> None:
        with self._lock:
            self._probando = False
            if self._estado == EstadoCircuito.semiabierto:
                self._transicion(EstadoCircuito.abierto, "falló la llamada de prueba")
                return
            self._fallos += 1
            if self._fallos >= self._umbral:
                self._transicion(EstadoCircuito.abierto, f"{self._fallos} fallos consecutivos")

    def _registrar_exito(self) -> None:
        with self._lock:
            self._probando = False
            if self._estado == EstadoCircuito.semiabierto:
                self._exitos_semiabierto += 1
                if self._exitos_semiabierto >= self._exitos_para_cerrar:
                    self._transicion(EstadoCircuito.cerrado, "la llamada de prueba funcionó")
            else:
                self._fallos = 0

    def _transicion(self, nuevo: EstadoCircuito, motivo: str) -> None:
        anterior = self._estado
        self._estado = nuevo
        self._probando = False
        if nuevo == EstadoCircuito.abierto:
            self._abierto_desde = self._reloj()
        elif nuevo == EstadoCircuito.cerrado:
            self._fallos = 0
        elif nuevo == EstadoCircuito.semiabierto:
            self._exitos_semiabierto = 0
        if anterior != nuevo:
            self.transiciones.append(f"{anterior.ingles} → {nuevo.ingles}: {motivo}")
