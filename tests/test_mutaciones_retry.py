
import pytest

from app.infrastructure.resilience.retry import calcular_espera, reintentar


def test_calcular_espera_respeta_limite_predeterminado():
    assert calcular_espera(10) == 8.0


def test_reintentar_utiliza_tres_intentos_por_defecto():
    llamadas = {"total": 0}

    def funcion_fallida():
        llamadas["total"] += 1
        raise ValueError("Error de prueba")

    try:
        reintentar(funcion_fallida, dormir=lambda _: None)
    except ValueError:
        pass

    assert llamadas["total"] == 3


def test_calcular_espera_aplica_jitter_sobre_la_espera_calculada():
    espera = calcular_espera(
        intento=3,
        base_s=2.0,
        factor=2.0,
        max_s=20.0,
        jitter=0.2,
        aleatorio=lambda: 1.0,
    )

    assert espera == pytest.approx(9.6)


def test_reintentar_respeta_limite_predeterminado_de_espera():
    esperas = []

    def funcion_fallida():
        raise ValueError("Error de prueba")

    with pytest.raises(ValueError):
        reintentar(
            funcion_fallida,
            intentos=3,
            base_s=5.0,
            factor=2.0,
            jitter=0.0,
            dormir=esperas.append,
        )

    assert esperas == [5.0, 8.0]


def test_reintentar_utiliza_jitter_predeterminado():
    esperas = []
    llamadas = {"total": 0}

    def funcion_falla_una_vez():
        llamadas["total"] += 1

        if llamadas["total"] == 1:
            raise ValueError("Error temporal")

        return "correcto"

    resultado = reintentar(
        funcion_falla_una_vez,
        intentos=2,
        base_s=2.0,
        factor=2.0,
        dormir=esperas.append,
        aleatorio=lambda: 1.0,
    )

    assert resultado == "correcto"
    assert esperas == [pytest.approx(2.2)]
