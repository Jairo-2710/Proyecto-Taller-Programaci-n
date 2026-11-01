"""Componente de análisis y optimización por reglas de decisión.

Indicador de utilización de un equipo en un periodo:

    utilización = horas de asignación activa dentro del periodo
                  / (días del periodo × horas operativas por día)        (tope 1.0)
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..domain.asignaciones.ports import AsignacionRepository
from ..domain.inventario.ports import EquipoRepository, ZonaRepository
from ..domain.mantenimiento.ports import IncidenteRepository, MantenimientoRepository
from ..domain.shared.enums import EstadoEquipo, EstadoIncidente, TipoEquipo
from ..domain.shared.ports import Reloj
from .parametros import ParametrosAnalisis

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@dataclass
class UtilizacionEquipo:
    equipo_id: int
    codigo: str
    zona_id: int
    zona: str
    tipo: TipoEquipo
    asignaciones: int
    horas_asignadas: float
    utilizacion: float
    clasificacion: str  # alta | normal | baja
    incidentes: int


@dataclass
class DemandaZona:
    zona_id: int
    zona: str
    equipos: int
    asignaciones: int
    horas_asignadas: float
    utilizacion: float
    por_dia_semana: dict[str, float]
    por_hora: dict[int, float]


@dataclass
class Demanda:
    desde: datetime
    hasta: datetime
    datos_suficientes: bool
    mensaje: str | None
    zonas: list[DemandaZona]


@dataclass
class IncidentesEquipo:
    equipo_id: int
    codigo: str
    incidentes: int
    abiertos: int
    resueltos: int
    tiempo_medio_resolucion_horas: float | None


@dataclass
class Recomendacion:
    tipo: str
    prioridad: str
    mensaje: str
    zona_id: int | None = None
    equipo_ids: list[int] = field(default_factory=list)


@dataclass
class Recomendaciones:
    desde: datetime
    hasta: datetime
    datos_suficientes: bool
    recomendaciones: list[Recomendacion]


@dataclass
class Resumen:
    equipos_activos: int
    equipos_por_estado: dict[str, int]
    equipos_por_zona: dict[str, int]
    asignaciones_en_curso: int
    incidentes_abiertos: int
    mantenimientos_abiertos: int


def _horas_solape(ini_a: datetime, fin_a: datetime, ini_b: datetime, fin_b: datetime) -> float:
    ini, fin = max(ini_a, ini_b), min(fin_a, fin_b)
    return max((fin - ini).total_seconds() / 3600, 0.0)


class AnalisisService:
    def __init__(
        self,
        equipos: EquipoRepository,
        zonas: ZonaRepository,
        asignaciones: AsignacionRepository,
        incidentes: IncidenteRepository,
        mantenimientos: MantenimientoRepository,
        reloj: Reloj,
        parametros: ParametrosAnalisis,
    ):
        self._equipos = equipos
        self._zonas = zonas
        self._asignaciones = asignaciones
        self._incidentes = incidentes
        self._mantenimientos = mantenimientos
        self._reloj = reloj
        self._p = parametros

    # ------------------------------------------------------------------ utilidades
    def _horas_base(self, desde: datetime, hasta: datetime) -> float:
        return max((hasta - desde).total_seconds() / 86400, 0.0) * self._p.horas_operativas_dia

    def _clasificar(self, utilizacion: float) -> str:
        if utilizacion >= self._p.umbral_utilizacion_alta:
            return "alta"
        if utilizacion < self._p.umbral_utilizacion_baja:
            return "baja"
        return "normal"

    def _datos_suficientes(self, desde: datetime, hasta: datetime, total: int) -> tuple[bool, str | None]:
        if (hasta - desde) < timedelta(days=self._p.min_dias_periodo_analisis):
            return False, (
                f"El periodo es menor a {self._p.min_dias_periodo_analisis} días; "
                "amplíelo para detectar patrones."
            )
        if total < self._p.min_asignaciones_analisis:
            return False, (
                f"Solo hay {total} asignaciones en el periodo (mínimo {self._p.min_asignaciones_analisis}); "
                "aún no hay información suficiente para detectar patrones."
            )
        return True, None

    # ------------------------------------------------------------------ indicadores
    def utilizacion_por_equipo(
        self, desde: datetime, hasta: datetime, zona_id: int | None = None
    ) -> list[UtilizacionEquipo]:
        zonas = {z.id: z.nombre for z in self._zonas.listar()}
        equipos = sorted(
            (e for e in self._equipos.listar_activos() if zona_id is None or e.zona_id == zona_id),
            key=lambda e: e.codigo,
        )
        horas: dict[int, float] = defaultdict(float)
        cantidad: dict[int, int] = defaultdict(int)
        for a in self._asignaciones.activas_en_rango(desde, hasta):
            horas[a.equipo_id] += _horas_solape(a.inicio, a.fin, desde, hasta)
            cantidad[a.equipo_id] += 1
        incidentes: dict[int, int] = defaultdict(int)
        for i in self._incidentes.reportados_en_rango(desde, hasta):
            incidentes[i.equipo_id] += 1

        base = self._horas_base(desde, hasta)
        resultado = []
        for e in equipos:
            util = min(horas[e.id] / base, 1.0) if base else 0.0
            resultado.append(
                UtilizacionEquipo(
                    equipo_id=e.id,
                    codigo=e.codigo,
                    zona_id=e.zona_id,
                    zona=zonas.get(e.zona_id, "?"),
                    tipo=e.tipo,
                    asignaciones=cantidad[e.id],
                    horas_asignadas=round(horas[e.id], 2),
                    utilizacion=round(util, 4),
                    clasificacion=self._clasificar(util),
                    incidentes=incidentes[e.id],
                )
            )
        return resultado

    def demanda_por_zona(self, desde: datetime, hasta: datetime) -> Demanda:
        zonas = sorted(self._zonas.listar(), key=lambda z: z.nombre)
        todos = self._equipos.todos()
        zona_de_equipo = {e.id: e.zona_id for e in todos}
        equipos_zona: dict[int, int] = defaultdict(int)
        for e in todos:
            if e.activo:
                equipos_zona[e.zona_id] += 1

        horas: dict[int, float] = defaultdict(float)
        cantidad: dict[int, int] = defaultdict(int)
        por_dia: dict[int, list[float]] = defaultdict(lambda: [0.0] * 7)
        por_hora: dict[int, list[float]] = defaultdict(lambda: [0.0] * 24)

        asignaciones = self._asignaciones.activas_en_rango(desde, hasta)
        for a in asignaciones:
            zona_id = zona_de_equipo.get(a.equipo_id)
            if zona_id is None:
                continue
            ini, fin = max(a.inicio, desde), min(a.fin, hasta)
            cantidad[zona_id] += 1
            horas[zona_id] += (fin - ini).total_seconds() / 3600
            tramo = ini.replace(minute=0, second=0, microsecond=0)
            while tramo < fin:
                parte = _horas_solape(ini, fin, tramo, tramo + timedelta(hours=1))
                por_hora[zona_id][tramo.hour] += parte
                por_dia[zona_id][tramo.weekday()] += parte
                tramo += timedelta(hours=1)

        base = self._horas_base(desde, hasta)
        resultado = []
        for z in zonas:
            n = equipos_zona[z.id]
            util = min(horas[z.id] / (n * base), 1.0) if n and base else 0.0
            resultado.append(
                DemandaZona(
                    zona_id=z.id,
                    zona=z.nombre,
                    equipos=n,
                    asignaciones=cantidad[z.id],
                    horas_asignadas=round(horas[z.id], 2),
                    utilizacion=round(util, 4),
                    por_dia_semana={DIAS[i]: round(v, 2) for i, v in enumerate(por_dia[z.id])},
                    por_hora={h: round(v, 2) for h, v in enumerate(por_hora[z.id])},
                )
            )
        suficientes, mensaje = self._datos_suficientes(desde, hasta, len(asignaciones))
        return Demanda(desde, hasta, suficientes, mensaje, resultado)

    def incidentes_por_equipo(self, desde: datetime, hasta: datetime) -> list[IncidentesEquipo]:
        codigos = {e.id: e.codigo for e in self._equipos.todos()}
        grupos: dict[int, list] = defaultdict(list)
        for i in self._incidentes.reportados_en_rango(desde, hasta):
            grupos[i.equipo_id].append(i)

        resultado = []
        for equipo_id, lista in grupos.items():
            resueltos = [i for i in lista if i.estado == EstadoIncidente.resuelto and i.fecha_cierre]
            tiempos = [(i.fecha_cierre - i.fecha_reporte).total_seconds() / 3600 for i in resueltos]
            resultado.append(
                IncidentesEquipo(
                    equipo_id=equipo_id,
                    codigo=codigos.get(equipo_id, "?"),
                    incidentes=len(lista),
                    abiertos=len([i for i in lista if i.estado != EstadoIncidente.resuelto]),
                    resueltos=len(resueltos),
                    tiempo_medio_resolucion_horas=round(sum(tiempos) / len(tiempos), 2) if tiempos else None,
                )
            )
        resultado.sort(key=lambda r: (-r.incidentes, r.codigo))
        return resultado

    # ------------------------------------------------------------------ recomendaciones
    def recomendaciones(self, desde: datetime, hasta: datetime) -> Recomendaciones:
        p = self._p
        demanda = self.demanda_por_zona(desde, hasta)
        utilizacion = self.utilizacion_por_equipo(desde, hasta)
        lista: list[Recomendacion] = []

        # Reglas 1 y 2: dependen de que haya historial suficiente.
        if demanda.datos_suficientes:
            con_equipos = [z for z in demanda.zonas if z.equipos > 0]
            altas = [z for z in con_equipos if z.utilizacion >= p.umbral_utilizacion_alta]
            bajas = [z for z in con_equipos if z.utilizacion < p.umbral_zona_baja]
            for alta in altas:
                for baja in bajas:
                    lista.append(
                        Recomendacion(
                            tipo="redistribuir_demanda",
                            prioridad="alta",
                            zona_id=alta.zona_id,
                            mensaje=(
                                f"La zona '{alta.zona}' tiene una utilización de {alta.utilizacion:.0%} mientras "
                                f"'{baja.zona}' tiene {baja.utilizacion:.0%}. Considere dirigir a '{baja.zona}' "
                                "las solicitudes cuyos requisitos sean compatibles."
                            ),
                        )
                    )
            por_zona: dict[int, list[UtilizacionEquipo]] = defaultdict(list)
            for u in utilizacion:
                if u.clasificacion == "baja":
                    por_zona[u.zona_id].append(u)
            for zona_id, equipos in por_zona.items():
                muestra = ", ".join(e.codigo for e in equipos[:10])
                extra = f" y {len(equipos) - 10} más" if len(equipos) > 10 else ""
                lista.append(
                    Recomendacion(
                        tipo="equipos_subutilizados",
                        prioridad="baja",
                        zona_id=zona_id,
                        equipo_ids=[e.equipo_id for e in equipos],
                        mensaje=(
                            f"{len(equipos)} equipo(s) de '{equipos[0].zona}' con utilización inferior a "
                            f"{p.umbral_utilizacion_baja:.0%}: {muestra}{extra}. Verifique si sus características "
                            "o ubicación limitan su asignación."
                        ),
                    )
                )

        # Regla 3: reincidencia de fallas.
        for u in utilizacion:
            if u.incidentes >= p.incidentes_para_revision:
                lista.append(
                    Recomendacion(
                        tipo="revision_tecnica",
                        prioridad="alta",
                        zona_id=u.zona_id,
                        equipo_ids=[u.equipo_id],
                        mensaje=(
                            f"El equipo {u.codigo} acumula {u.incidentes} incidentes en el periodo. "
                            "Programe una revisión o mantenimiento preventivo."
                        ),
                    )
                )

        equipos_por_id = {e.id: e for e in self._equipos.todos()}

        # Regla 4: mantenimientos abiertos por demasiado tiempo.
        limite = self._reloj() - timedelta(days=p.dias_mantenimiento_prolongado)
        for mant in self._mantenimientos.abiertos_iniciados_antes_de(limite):
            equipo = equipos_por_id.get(mant.equipo_id)
            if equipo is None:
                continue
            lista.append(
                Recomendacion(
                    tipo="mantenimiento_prolongado",
                    prioridad="media",
                    zona_id=equipo.zona_id,
                    equipo_ids=[equipo.id],
                    mensaje=(
                        f"El equipo {equipo.codigo} lleva más de {p.dias_mantenimiento_prolongado} días en "
                        "mantenimiento. Revise el avance o evalúe su reemplazo."
                    ),
                )
            )

        # Regla 5: equipos fuera de servicio sin mantenimiento registrado.
        for equipo in self._equipos.listar_activos():
            if equipo.estado == EstadoEquipo.fuera_de_servicio:
                lista.append(
                    Recomendacion(
                        tipo="equipo_sin_atencion",
                        prioridad="alta",
                        zona_id=equipo.zona_id,
                        equipo_ids=[equipo.id],
                        mensaje=(
                            f"El equipo {equipo.codigo} está fuera de servicio sin mantenimiento abierto. "
                            "Programe su atención."
                        ),
                    )
                )

        orden = {"alta": 0, "media": 1, "baja": 2}
        lista.sort(key=lambda r: orden[r.prioridad])
        return Recomendaciones(desde, hasta, demanda.datos_suficientes, lista)

    def resumen(self) -> Resumen:
        activos = self._equipos.listar_activos()
        por_estado = {e.value: 0 for e in EstadoEquipo}
        por_zona_id: dict[int, int] = defaultdict(int)
        for e in activos:
            por_estado[e.estado.value] += 1
            por_zona_id[e.zona_id] += 1
        nombres = {z.id: z.nombre for z in self._zonas.listar()}
        return Resumen(
            equipos_activos=len(activos),
            equipos_por_estado=por_estado,
            equipos_por_zona={nombres[z]: n for z, n in por_zona_id.items() if z in nombres},
            asignaciones_en_curso=self._asignaciones.contar_en_curso(self._reloj()),
            incidentes_abiertos=self._incidentes.contar_abiertos(),
            mantenimientos_abiertos=self._mantenimientos.contar_abiertos(),
        )
