"""Adaptadores de APIs públicas (con transporte falso), DuckDB y el servicio de análisis (con mocks)."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.application.analitica import DatosAbiertosService, normalizar_territorial
from app.domain.analitica.entities import ConsultaFuente
from app.domain.shared.enums import EstadoCircuito
from app.domain.shared.errors import FuenteNoDisponibleError
from app.infrastructure.analytics.duckdb_motor import DuckDbMotor
from app.infrastructure.opendata.fuentes import DatosGovCoAdapter
from app.infrastructure.opendata.transport import ErrorPermanente, ErrorTransitorio
from app.infrastructure.resilience.circuit_breaker import CircuitBreaker

AHORA = datetime(2026, 10, 31, 12, 0)
MUNICIPIOS = [
    {"cod_mpio": "05001", "nom_mpio": "Medellín", "dpto": "Antioquia"},
    {"cod_mpio": "05002", "nom_mpio": "Abejorral", "dpto": "Antioquia"},
    {"cod_mpio": "11001", "nom_mpio": "Bogotá", "dpto": "Bogotá D.C."},
]


def _adaptador(transporte, umbral=3, intentos=3):
    return DatosGovCoAdapter(
        base_url="https://www.datos.gov.co",
        dataset_id="gdxc-w37w",
        transporte=transporte,
        breaker=CircuitBreaker("datos.gov.co", umbral_fallos=umbral, tiempo_recuperacion_s=30, reloj=lambda: 0.0,
                               excepciones_que_cuentan=(ErrorTransitorio,)),
        reloj=lambda: AHORA,
        intentos=intentos,
        dormir=lambda s: None,
    )


def test_consulta_correcta():
    t = MagicMock()
    t.get_json.return_value = MUNICIPIOS
    r = _adaptador(t).consultar(100)
    assert len(r.registros) == 3 and not r.desde_cache
    url, params, *_ = t.get_json.call_args.args
    assert url.endswith("/resource/gdxc-w37w.json") and params == {"$limit": "100"}


def test_reintenta_errores_transitorios():
    t = MagicMock()
    t.get_json.side_effect = [ErrorTransitorio("503"), ErrorTransitorio("503"), MUNICIPIOS]
    assert len(_adaptador(t).consultar(10).registros) == 3
    assert t.get_json.call_count == 3


def test_circuito_abre_y_ya_no_llama_a_la_api():
    t = MagicMock()
    t.get_json.side_effect = ErrorTransitorio("caída")
    a = _adaptador(t)
    with pytest.raises(FuenteNoDisponibleError):
        a.consultar(10)  # 3 intentos -> 3 fallos -> OPEN
    assert a.estado().estado_circuito == EstadoCircuito.abierto
    llamadas = t.get_json.call_count
    with pytest.raises(FuenteNoDisponibleError):
        a.consultar(10)
    assert t.get_json.call_count == llamadas


def test_si_la_api_cae_devuelve_ultimo_dato_bueno():
    t = MagicMock()
    t.get_json.side_effect = [MUNICIPIOS] + [ErrorTransitorio("caída")] * 3
    a = _adaptador(t)
    a.consultar(10)
    r = a.consultar(10)
    assert r.desde_cache and len(r.registros) == 3


def test_error_permanente_no_se_reintenta_ni_cuenta():
    t = MagicMock()
    t.get_json.side_effect = ErrorPermanente("404")
    a = _adaptador(t)
    with pytest.raises(FuenteNoDisponibleError):
        a.consultar(10)
    assert t.get_json.call_count == 1
    assert a.estado().fallos_consecutivos == 0


def test_respuesta_que_no_es_lista_es_error():
    t = MagicMock()
    t.get_json.return_value = {"error": True}
    with pytest.raises(FuenteNoDisponibleError):
        _adaptador(t).consultar(10)


def test_duckdb_estadisticas_descriptivas():
    filas = [{"g": "a", "v": 1}, {"g": "a", "v": 3}, {"g": "b", "v": 10}]
    r = DuckDbMotor().ejecutar(
        {"t": filas}, "SELECT g, AVG(v) AS media, MEDIAN(v) AS mediana, STDDEV_SAMP(v) AS desv FROM t GROUP BY g ORDER BY g"
    )
    assert r[0]["media"] == 2 and r[0]["mediana"] == 2 and round(r[0]["desv"], 3) == 1.414
    assert r[1]["desv"] is None


def test_duckdb_rechaza_nombre_de_tabla_invalido():
    with pytest.raises(ValueError):
        DuckDbMotor().ejecutar({"x; DROP": []}, "SELECT 1")


def test_normalizar_tolera_nombres_de_columna():
    assert normalizar_territorial({"departamento": "Cauca", "municipio": "Popayán", "codigo_dane": 19001}) == {
        "codigo_municipio": "19001", "municipio": "Popayán", "departamento": "Cauca"}


def _fuente(nombre, registros=None, error=None):
    f = MagicMock()
    f.nombre = nombre
    f.estado.return_value.estado_circuito = EstadoCircuito.cerrado
    if error:
        f.consultar.side_effect = FuenteNoDisponibleError(error)
    else:
        f.consultar.return_value = ConsultaFuente(nombre, registros, AHORA, EstadoCircuito.cerrado)
    return f


def test_servicio_inyecta_fuentes_falsas_y_analiza_con_duckdb():
    svc = DatosAbiertosService(_fuente("datos.gov.co", MUNICIPIOS), _fuente("DANE", MUNICIPIOS), DuckDbMotor(), lambda: AHORA)
    r = svc.analizar()
    assert r.ranking_departamentos[0]["departamento"] == "Antioquia"
    assert r.ranking_departamentos[0]["municipios"] == 2
    assert r.estadisticas_departamentos is not None and not r.advertencias


def test_servicio_continua_si_una_fuente_falla():
    svc = DatosAbiertosService(_fuente("datos.gov.co", error="caída"), _fuente("DANE", MUNICIPIOS), DuckDbMotor(), lambda: AHORA)
    r = svc.analizar()
    assert r.ranking_departamentos == [] and r.estadisticas_departamentos is not None
    assert r.fuentes[0].error and any("datos.gov.co no disponible" in a for a in r.advertencias)


def test_servicio_usa_motor_falso():
    motor = MagicMock()
    motor.ejecutar.return_value = []
    DatosAbiertosService(_fuente("datos.gov.co", MUNICIPIOS), _fuente("DANE", MUNICIPIOS), motor, lambda: AHORA).analizar()
    assert motor.ejecutar.call_count == 2
