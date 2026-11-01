"""Adaptadores de salida hacia las APIs públicas colombianas (datos.gov.co y DANE).

Ambas publican sus datos con la API SODA de Socrata:  {base}/resource/{dataset}.json?$limit=N
Cada fuente tiene su propio circuit breaker, de modo que la caída de una no bloquea a la otra.

Por llamada:  retry (backoff exponencial)  ─▶  circuit breaker  ─▶  transporte HTTP
Si la API falla se devuelve el último dato bueno guardado (si existe), marcado `desde_cache=True`.
"""
import time
from collections.abc import Callable
from datetime import datetime

from ...domain.analitica.entities import ConsultaFuente, EstadoFuente
from ...domain.shared.errors import FuenteNoDisponibleError
from ..resilience.circuit_breaker import CircuitBreaker, CircuitoAbiertoError
from ..resilience.retry import reintentar
from .transport import ErrorPermanente, ErrorTransitorio, TransporteHttp


class FuenteSocrata:
    """Implementa el puerto `FuenteDatosAbiertos`."""

    def __init__(
        self,
        nombre: str,
        descripcion: str,
        base_url: str,
        dataset_id: str,
        transporte: TransporteHttp,
        breaker: CircuitBreaker,
        reloj: Callable[[], datetime],
        *,
        intentos: int = 3,
        base_s: float = 0.5,
        timeout_s: float = 10.0,
        app_token: str = "",
        dormir: Callable[[float], None] = time.sleep,
    ):
        self.nombre = nombre
        self._descripcion = descripcion
        self.url = f"{base_url.rstrip('/')}/resource/{dataset_id}.json"
        self._transporte = transporte
        self._breaker = breaker
        self._reloj = reloj
        self._intentos = intentos
        self._base_s = base_s
        self._timeout_s = timeout_s
        self._app_token = app_token
        self._dormir = dormir
        self._ultimo_bueno: tuple[list[dict], datetime] | None = None

    def consultar(self, limite: int) -> ConsultaFuente:
        parametros = {"$limit": str(limite)}
        encabezados = {"Accept": "application/json"}
        if self._app_token:
            encabezados["X-App-Token"] = self._app_token

        def una_llamada():
            return self._breaker.ejecutar(
                lambda: self._transporte.get_json(self.url, parametros, encabezados, self._timeout_s)
            )

        try:
            datos = reintentar(
                una_llamada,
                intentos=self._intentos,
                base_s=self._base_s,
                reintentables=(ErrorTransitorio,),  # un circuito abierto o un 404 no se reintentan
                dormir=self._dormir,
            )
            if not isinstance(datos, list):
                raise ErrorPermanente(f"Respuesta inesperada de {self.url}: se esperaba una lista JSON")
        except (CircuitoAbiertoError, ErrorTransitorio, ErrorPermanente) as error:
            if self._ultimo_bueno is not None:
                registros, momento = self._ultimo_bueno
                return ConsultaFuente(self.nombre, registros, momento, self._breaker.estado, desde_cache=True)
            raise FuenteNoDisponibleError(
                str(error), info={"fuente": self.nombre, "estado_circuito": self._breaker.estado.value}
            ) from error

        momento = self._reloj()
        self._ultimo_bueno = (datos, momento)
        return ConsultaFuente(self.nombre, datos, momento, self._breaker.estado)

    def estado(self) -> EstadoFuente:
        return EstadoFuente(
            fuente=self.nombre,
            descripcion=self._descripcion,
            url=self.url,
            estado_circuito=self._breaker.estado,
            fallos_consecutivos=self._breaker.fallos_consecutivos,
            transiciones=list(self._breaker.transiciones),
        )


class DatosGovCoAdapter(FuenteSocrata):
    """Portal de datos abiertos del Gobierno de Colombia."""

    def __init__(self, **kwargs):
        super().__init__(
            nombre="datos.gov.co",
            descripcion="Portal de datos abiertos del Gobierno de Colombia (API SODA)",
            **kwargs,
        )


class DaneAdapter(FuenteSocrata):
    """Datos del Departamento Administrativo Nacional de Estadística."""

    def __init__(self, **kwargs):
        super().__init__(
            nombre="DANE",
            descripcion="Departamento Administrativo Nacional de Estadística (datos publicados vía SODA)",
            **kwargs,
        )
