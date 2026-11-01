"""Análisis de datos con DuckDB: estadísticas descriptivas y datos abiertos colombianos.

Las consultas SQL viven aquí (son definiciones analíticas del negocio); el motor que las ejecuta
se inyecta como puerto `MotorAnalitico`, por lo que los casos de uso se prueban con un doble.
"""
from dataclasses import dataclass, field
from datetime import datetime

from ..domain.analitica.entities import EstadoFuente
from ..domain.analitica.ports import FuenteDatosAbiertos, MotorAnalitico
from ..domain.asignaciones.ports import AsignacionRepository
from ..domain.inventario.ports import EquipoRepository, ZonaRepository
from ..domain.shared.enums import EstadoCircuito
from ..domain.shared.errors import FuenteNoDisponibleError
from ..domain.shared.ports import Reloj

# --------------------------------------------------------------------------- consultas SQL
SQL_EQUIPOS_POR_ZONA_TIPO = """
SELECT zona, tipo,
       COUNT(*)                                             AS equipos,
       ROUND(AVG(ram_gb), 2)                                AS ram_promedio_gb,
       MIN(ram_gb)                                          AS ram_min_gb,
       MAX(ram_gb)                                          AS ram_max_gb,
       ROUND(COALESCE(STDDEV_SAMP(ram_gb), 0), 2)           AS ram_desv_est,
       ROUND(AVG(almacenamiento_gb), 2)                     AS almacenamiento_promedio_gb,
       ROUND(100.0 * SUM(CASE WHEN estado = 'disponible' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_disponible
FROM equipos
GROUP BY zona, tipo
ORDER BY zona, tipo
"""

SQL_ASIGNACIONES_POR_ZONA = """
SELECT zona,
       COUNT(*)                                          AS asignaciones,
       COUNT(DISTINCT equipo_id)                         AS equipos_usados,
       ROUND(SUM(horas), 2)                              AS horas_totales,
       ROUND(AVG(horas), 2)                              AS horas_promedio,
       ROUND(MEDIAN(horas), 2)                           AS horas_mediana,
       ROUND(QUANTILE_CONT(horas, 0.9), 2)               AS horas_p90,
       ROUND(COALESCE(STDDEV_SAMP(horas), 0), 2)         AS horas_desv_est
FROM asignaciones
GROUP BY zona
ORDER BY horas_totales DESC
"""

SQL_HORAS_PICO = """
SELECT EXTRACT(hour FROM CAST(inicio AS TIMESTAMP)) AS hora_inicio,
       COUNT(*)                                     AS asignaciones
FROM asignaciones
GROUP BY 1
ORDER BY asignaciones DESC, hora_inicio
LIMIT 5
"""

SQL_RANKING_DEPARTAMENTOS = """
SELECT departamento, COUNT(*) AS municipios
FROM territorio
GROUP BY departamento
ORDER BY municipios DESC, departamento
LIMIT 10
"""

SQL_ESTADISTICAS_DEPARTAMENTOS = """
WITH por_departamento AS (
    SELECT departamento, COUNT(*) AS n FROM territorio GROUP BY departamento
)
SELECT SUM(n)                                    AS total_municipios,
       COUNT(*)                                  AS total_departamentos,
       ROUND(AVG(n), 2)                          AS promedio_por_departamento,
       MEDIAN(n)                                 AS mediana,
       ROUND(COALESCE(STDDEV_SAMP(n), 0), 2)     AS desv_est,
       MIN(n)                                    AS minimo,
       MAX(n)                                    AS maximo
FROM por_departamento
"""


# --------------------------------------------------------------------------- estadísticas del proyecto
@dataclass
class EstadisticasEquipos:
    por_zona_tipo: list[dict]


@dataclass
class EstadisticasAsignaciones:
    desde: datetime
    hasta: datetime
    por_zona: list[dict]
    horas_pico: list[dict]


class EstadisticasService:
    """Estadísticas descriptivas del propio sistema (equipos y asignaciones) calculadas con DuckDB."""

    def __init__(
        self,
        equipos: EquipoRepository,
        zonas: ZonaRepository,
        asignaciones: AsignacionRepository,
        motor: MotorAnalitico,
    ):
        self._equipos = equipos
        self._zonas = zonas
        self._asignaciones = asignaciones
        self._motor = motor

    def equipos(self) -> EstadisticasEquipos:
        zonas = {z.id: z.nombre for z in self._zonas.listar()}
        filas = [
            {
                "zona": zonas.get(e.zona_id, "?"),
                "tipo": e.tipo.value,
                "estado": e.estado.value,
                "ram_gb": e.ram_gb,
                "almacenamiento_gb": e.almacenamiento_gb,
            }
            for e in self._equipos.listar_activos()
        ]
        if not filas:
            return EstadisticasEquipos(por_zona_tipo=[])
        return EstadisticasEquipos(por_zona_tipo=self._motor.ejecutar({"equipos": filas}, SQL_EQUIPOS_POR_ZONA_TIPO))

    def asignaciones(self, desde: datetime, hasta: datetime) -> EstadisticasAsignaciones:
        zona_de_equipo = {e.id: e.zona_id for e in self._equipos.todos()}
        zonas = {z.id: z.nombre for z in self._zonas.listar()}
        filas = [
            {
                "zona": zonas.get(zona_de_equipo.get(a.equipo_id), "?"),
                "equipo_id": a.equipo_id,
                "inicio": a.inicio.isoformat(),
                "fin": a.fin.isoformat(),
                "horas": (a.fin - a.inicio).total_seconds() / 3600,
            }
            for a in self._asignaciones.activas_en_rango(desde, hasta)
        ]
        if not filas:
            return EstadisticasAsignaciones(desde, hasta, [], [])
        tablas = {"asignaciones": filas}
        return EstadisticasAsignaciones(
            desde,
            hasta,
            por_zona=self._motor.ejecutar(tablas, SQL_ASIGNACIONES_POR_ZONA),
            horas_pico=self._motor.ejecutar(tablas, SQL_HORAS_PICO),
        )


# --------------------------------------------------------------------------- datos abiertos
_CLAVES_DEPARTAMENTO = ("dpto", "departamento", "nom_dpto", "nom_departamento", "nombre_departamento")
_CLAVES_MUNICIPIO = ("nom_mpio", "municipio", "nom_municipio", "nombre_municipio")
_CLAVES_CODIGO = ("cod_mpio", "codigo_municipio", "cod_municipio", "codigo_dane", "divipola")


def _primero(registro: dict, claves: tuple[str, ...]) -> str | None:
    for clave in claves:
        valor = registro.get(clave)
        if valor not in (None, ""):
            return str(valor).strip()
    return None


def normalizar_territorial(registro: dict) -> dict:
    """Toma un registro DIVIPOLA (los nombres de columna pueden variar) y lo lleva a un esquema fijo."""
    return {
        "codigo_municipio": _primero(registro, _CLAVES_CODIGO),
        "municipio": _primero(registro, _CLAVES_MUNICIPIO),
        "departamento": _primero(registro, _CLAVES_DEPARTAMENTO) or "SIN DATO",
    }


@dataclass
class ResultadoFuente:
    fuente: str
    estado_circuito: EstadoCircuito
    registros: int = 0
    desde_cache: bool = False
    error: str | None = None


@dataclass
class AnalisisDatosAbiertos:
    fuentes: list[ResultadoFuente]
    ranking_departamentos: list[dict] = field(default_factory=list)  # fuente: datos.gov.co
    estadisticas_departamentos: dict | None = None  # fuente: DANE
    advertencias: list[str] = field(default_factory=list)


class DatosAbiertosService:
    """Consulta dos APIs públicas colombianas y analiza sus datos JSON con DuckDB.

    - datos.gov.co  -> ranking de departamentos por número de municipios
    - DANE          -> estadísticas descriptivas de municipios por departamento
    Si una fuente falla (circuito abierto o agotó los reintentos) el análisis continúa con la otra.
    """

    def __init__(
        self,
        datos_gov_co: FuenteDatosAbiertos,
        dane: FuenteDatosAbiertos,
        motor: MotorAnalitico,
        reloj: Reloj,
        limite_registros: int = 2000,
    ):
        self._datos_gov_co = datos_gov_co
        self._dane = dane
        self._motor = motor
        self._reloj = reloj
        self._limite = limite_registros

    def estados(self) -> list[EstadoFuente]:
        return [self._datos_gov_co.estado(), self._dane.estado()]

    def analizar(self) -> AnalisisDatosAbiertos:
        resultado = AnalisisDatosAbiertos(fuentes=[])
        territorio_gov = self._cargar(self._datos_gov_co, resultado)
        territorio_dane = self._cargar(self._dane, resultado)

        if territorio_gov:
            resultado.ranking_departamentos = self._motor.ejecutar(
                {"territorio": territorio_gov}, SQL_RANKING_DEPARTAMENTOS
            )
        if territorio_dane:
            filas = self._motor.ejecutar({"territorio": territorio_dane}, SQL_ESTADISTICAS_DEPARTAMENTOS)
            resultado.estadisticas_departamentos = filas[0] if filas else None
        for territorio, nombre in ((territorio_gov, "datos.gov.co"), (territorio_dane, "DANE")):
            if territorio and all(r["departamento"] == "SIN DATO" for r in territorio):
                resultado.advertencias.append(
                    f"{nombre}: no se reconocieron columnas de departamento/municipio en el dataset configurado."
                )
        return resultado

    def _cargar(self, fuente: FuenteDatosAbiertos, resultado: AnalisisDatosAbiertos) -> list[dict]:
        try:
            consulta = fuente.consultar(self._limite)
        except FuenteNoDisponibleError as error:
            estado = fuente.estado().estado_circuito
            resultado.fuentes.append(
                ResultadoFuente(fuente=fuente.nombre, estado_circuito=estado, error=error.mensaje)
            )
            resultado.advertencias.append(f"{fuente.nombre} no disponible: {error.mensaje}")
            return []
        resultado.fuentes.append(
            ResultadoFuente(
                fuente=fuente.nombre,
                estado_circuito=consulta.estado_circuito,
                registros=len(consulta.registros),
                desde_cache=consulta.desde_cache,
            )
        )
        if consulta.desde_cache:
            resultado.advertencias.append(f"{fuente.nombre}: se usaron los últimos datos guardados (la API falló).")
        return [normalizar_territorial(r) for r in consulta.registros]
