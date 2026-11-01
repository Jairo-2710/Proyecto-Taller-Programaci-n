"""Circuit breaker (3 estados) y retry con backoff exponencial, con reloj y sleep falsos."""
import pytest

from app.domain.shared.enums import EstadoCircuito
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker, CircuitoAbiertoError
from app.infrastructure.resilience.retry import calcular_espera, reintentar


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _falla():
    raise ConnectionError("caída")


def _breaker(reloj, **kw):
    return CircuitBreaker("api", umbral_fallos=3, tiempo_recuperacion_s=30, reloj=reloj, **kw)


def test_cerrado_a_abierto_tras_umbral_de_fallos():
    cb = _breaker(Reloj())
    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.ejecutar(_falla)
    assert cb.estado == EstadoCircuito.abierto


def test_abierto_rechaza_sin_llamar_a_la_api():
    cb = _breaker(Reloj())
    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.ejecutar(_falla)
    llamadas = []
    with pytest.raises(CircuitoAbiertoError):
        cb.ejecutar(lambda: llamadas.append(1))
    assert llamadas == []


def test_abierto_a_semiabierto_y_cierra_si_la_prueba_funciona():
    reloj = Reloj()
    cb = _breaker(reloj)
    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.ejecutar(_falla)
    reloj.t = 31
    assert cb.estado == EstadoCircuito.semiabierto
    assert cb.ejecutar(lambda: "ok") == "ok"
    assert cb.estado == EstadoCircuito.cerrado
    assert cb.fallos_consecutivos == 0


def test_semiabierto_vuelve_a_abrir_si_la_prueba_falla():
    reloj = Reloj()
    cb = _breaker(reloj)
    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.ejecutar(_falla)
    reloj.t = 31
    with pytest.raises(ConnectionError):
        cb.ejecutar(_falla)
    assert cb.estado == EstadoCircuito.abierto


def test_un_exito_reinicia_el_conteo_de_fallos():
    cb = _breaker(Reloj())
    for _ in range(2):
        with pytest.raises(ConnectionError):
            cb.ejecutar(_falla)
    cb.ejecutar(lambda: 1)
    assert cb.fallos_consecutivos == 0


def test_excepciones_que_no_cuentan_no_abren_el_circuito():
    cb = _breaker(Reloj(), excepciones_que_cuentan=(ConnectionError,))
    for _ in range(5):
        with pytest.raises(KeyError):
            cb.ejecutar(lambda: (_ for _ in ()).throw(KeyError("x")))
    assert cb.estado == EstadoCircuito.cerrado


def test_registra_transiciones():
    reloj = Reloj()
    cb = _breaker(reloj)
    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.ejecutar(_falla)
    reloj.t = 31
    cb.ejecutar(lambda: 1)
    assert [t.split(":")[0] for t in cb.transiciones] == ["CLOSED → OPEN", "OPEN → HALF_OPEN", "HALF_OPEN → CLOSED"]


def test_backoff_exponencial():
    assert [calcular_espera(i) for i in (1, 2, 3, 4)] == [0.5, 1.0, 2.0, 4.0]
    assert calcular_espera(10, max_s=8) == 8


def test_reintentar_espera_creciente_y_tiene_exito():
    esperas, intentos = [], []

    def funcion():
        intentos.append(1)
        if len(intentos) < 3:
            raise ConnectionError()
        return "ok"

    assert reintentar(funcion, jitter=0, dormir=esperas.append, reintentables=(ConnectionError,)) == "ok"
    assert esperas == [0.5, 1.0]


def test_reintentar_propaga_tras_agotar_intentos():
    esperas = []
    with pytest.raises(ConnectionError):
        reintentar(_falla, intentos=3, jitter=0, dormir=esperas.append)
    assert len(esperas) == 2


def test_reintentar_no_reintenta_errores_no_reintentables():
    esperas = []
    with pytest.raises(KeyError):
        reintentar(lambda: {}["x"], dormir=esperas.append, reintentables=(ConnectionError,))
    assert esperas == []
