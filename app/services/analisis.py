"""Componente de análisis y optimización (reglas de decisión sobre datos históricos).

Fórmula del indicador de utilización de un equipo en un periodo:

    utilización = horas de asignación activa dentro del periodo
                  / (días del periodo × HORAS_OPERATIVAS_DIA)        (tope 1.0)
"""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..config import ahora
from ..enums import EstadoAsignacion, EstadoEquipo, EstadoIncidente, Severidad
from ..models import Asignacion, Equipo, Incidente, Mantenimiento, Zona
from ..schemas import (
    DemandaOut,
    DemandaZonaOut,
    IncidentesEquipoOut,
    Recomendacion,
    RecomendacionesOut,
    ResumenOut,
    UtilizacionEquipoOut,
)

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _horas_solape(ini_a: datetime, fin_a: datetime, ini_b: datetime, fin_b: datetime) -> float:
    ini, fin = max(ini_a, ini_b), min(fin_a, fin_b)
    return max((fin - ini).total_seconds() / 3600, 0.0)


def _horas_operativas(desde: datetime, hasta: datetime) -> float:
    return max((hasta - desde).total_seconds() / 86400, 0.0) * config.HORAS_OPERATIVAS_DIA


def _asignaciones_en_rango(db: Session, desde: datetime, hasta: datetime) -> list[Asignacion]:
    return list(
        db.scalars(
            select(Asignacion).where(
                Asignacion.estado == EstadoAsignacion.activa,
                Asignacion.inicio < hasta,
                Asignacion.fin > desde,
            )
        )
    )


def _clasificar(utilizacion: float) -> str:
    if utilizacion >= config.UMBRAL_UTILIZACION_ALTA:
        return "alta"
    if utilizacion < config.UMBRAL_UTILIZACION_BAJA:
        return "baja"
    return "normal"


def utilizacion_por_equipo(
    db: Session, desde: datetime, hasta: datetime, zona_id: int | None = None
) -> list[UtilizacionEquipoOut]:
    consulta = select(Equipo).where(Equipo.activo.is_(True)).order_by(Equipo.codigo)
    if zona_id is not None:
        consulta = consulta.where(Equipo.zona_id == zona_id)
    equipos = list(db.scalars(consulta).unique())

    horas: dict[int, float] = defaultdict(float)
    cantidad: dict[int, int] = defaultdict(int)
    for a in _asignaciones_en_rango(db, desde, hasta):
        horas[a.equipo_id] += _horas_solape(a.inicio, a.fin, desde, hasta)
        cantidad[a.equipo_id] += 1

    incidentes = dict(
        db.execute(
            select(Incidente.equipo_id, func.count())
            .where(Incidente.fecha_reporte >= desde, Incidente.fecha_reporte < hasta)
            .group_by(Incidente.equipo_id)
        ).all()
    )

    base = _horas_operativas(desde, hasta)
    resultado = []
    for e in equipos:
        util = min(horas[e.id] / base, 1.0) if base else 0.0
        resultado.append(
            UtilizacionEquipoOut(
                equipo_id=e.id,
                codigo=e.codigo,
                zona_id=e.zona_id,
                zona=e.zona.nombre,
                tipo=e.tipo,
                asignaciones=cantidad[e.id],
                horas_asignadas=round(horas[e.id], 2),
                utilizacion=round(util, 4),
                clasificacion=_clasificar(util),
                incidentes=incidentes.get(e.id, 0),
            )
        )
    return resultado


def _datos_suficientes(desde: datetime, hasta: datetime, total_asignaciones: int) -> tuple[bool, str | None]:
    if (hasta - desde) < timedelta(days=config.MIN_DIAS_PERIODO_ANALISIS):
        return False, f"El periodo es menor a {config.MIN_DIAS_PERIODO_ANALISIS} días; amplíelo para detectar patrones."
    if total_asignaciones < config.MIN_ASIGNACIONES_ANALISIS:
        return False, (
            f"Solo hay {total_asignaciones} asignaciones en el periodo "
            f"(mínimo {config.MIN_ASIGNACIONES_ANALISIS}); aún no hay información suficiente para detectar patrones."
        )
    return True, None


def demanda_por_zona(db: Session, desde: datetime, hasta: datetime) -> DemandaOut:
    zonas = list(db.scalars(select(Zona).order_by(Zona.nombre)))
    equipos_zona = dict(
        db.execute(select(Equipo.zona_id, func.count()).where(Equipo.activo.is_(True)).group_by(Equipo.zona_id)).all()
    )
    zona_de_equipo = dict(db.execute(select(Equipo.id, Equipo.zona_id)).all())

    horas: dict[int, float] = defaultdict(float)
    cantidad: dict[int, int] = defaultdict(int)
    por_dia: dict[int, list[float]] = defaultdict(lambda: [0.0] * 7)
    por_hora: dict[int, list[float]] = defaultdict(lambda: [0.0] * 24)

    asignaciones = _asignaciones_en_rango(db, desde, hasta)
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

    base = _horas_operativas(desde, hasta)
    resultado = []
    for z in zonas:
        n = equipos_zona.get(z.id, 0)
        util = min(horas[z.id] / (n * base), 1.0) if n and base else 0.0
        resultado.append(
            DemandaZonaOut(
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
    suficientes, mensaje = _datos_suficientes(desde, hasta, len(asignaciones))
    return DemandaOut(desde=desde, hasta=hasta, datos_suficientes=suficientes, mensaje=mensaje, zonas=resultado)


def incidentes_por_equipo(db: Session, desde: datetime, hasta: datetime) -> list[IncidentesEquipoOut]:
    codigos = dict(db.execute(select(Equipo.id, Equipo.codigo)).all())
    incidentes = db.scalars(
        select(Incidente).where(Incidente.fecha_reporte >= desde, Incidente.fecha_reporte < hasta)
    )
    grupos: dict[int, list[Incidente]] = defaultdict(list)
    for i in incidentes:
        grupos[i.equipo_id].append(i)

    resultado = []
    for equipo_id, lista in grupos.items():
        resueltos = [i for i in lista if i.estado == EstadoIncidente.resuelto and i.fecha_cierre]
        tiempos = [(i.fecha_cierre - i.fecha_reporte).total_seconds() / 3600 for i in resueltos]
        resultado.append(
            IncidentesEquipoOut(
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


def recomendaciones(db: Session, desde: datetime, hasta: datetime) -> RecomendacionesOut:
    """Aplica reglas de decisión sobre utilización, incidentes y estado de los equipos."""
    demanda = demanda_por_zona(db, desde, hasta)
    utilizacion = utilizacion_por_equipo(db, desde, hasta)
    lista: list[Recomendacion] = []

    # Reglas 1 y 2: dependen de que haya historial suficiente.
    if demanda.datos_suficientes:
        zonas_con_equipos = [z for z in demanda.zonas if z.equipos > 0]
        altas = [z for z in zonas_con_equipos if z.utilizacion >= config.UMBRAL_UTILIZACION_ALTA]
        bajas = [z for z in zonas_con_equipos if z.utilizacion < config.UMBRAL_ZONA_BAJA]
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
        por_zona: dict[int, list[UtilizacionEquipoOut]] = defaultdict(list)
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
                        f"{config.UMBRAL_UTILIZACION_BAJA:.0%}: {muestra}{extra}. Verifique si sus características "
                        "o ubicación limitan su asignación."
                    ),
                )
            )

    # Regla 3: reincidencia de fallas.
    for u in utilizacion:
        if u.incidentes >= config.INCIDENTES_PARA_REVISION:
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

    # Regla 4: mantenimientos abiertos por demasiado tiempo.
    limite = ahora() - timedelta(days=config.DIAS_MANTENIMIENTO_PROLONGADO)
    prolongados = db.execute(
        select(Mantenimiento, Equipo)
        .join(Equipo, Equipo.id == Mantenimiento.equipo_id)
        .where(Mantenimiento.fin.is_(None), Mantenimiento.inicio < limite)
    ).all()
    for mant, equipo in prolongados:
        lista.append(
            Recomendacion(
                tipo="mantenimiento_prolongado",
                prioridad="media",
                zona_id=equipo.zona_id,
                equipo_ids=[equipo.id],
                mensaje=(
                    f"El equipo {equipo.codigo} lleva más de {config.DIAS_MANTENIMIENTO_PROLONGADO} días en "
                    "mantenimiento. Revise el avance o evalúe su reemplazo."
                ),
            )
        )

    # Regla 5: equipos fuera de servicio sin mantenimiento registrado.
    sin_atencion = db.scalars(
        select(Equipo).where(Equipo.activo.is_(True), Equipo.estado == EstadoEquipo.fuera_de_servicio)
    ).unique()
    for equipo in sin_atencion:
        lista.append(
            Recomendacion(
                tipo="equipo_sin_atencion",
                prioridad="alta",
                zona_id=equipo.zona_id,
                equipo_ids=[equipo.id],
                mensaje=f"El equipo {equipo.codigo} está fuera de servicio sin mantenimiento abierto. Programe su atención.",
            )
        )

    orden = {"alta": 0, "media": 1, "baja": 2}
    lista.sort(key=lambda r: orden[r.prioridad])
    return RecomendacionesOut(
        desde=desde, hasta=hasta, datos_suficientes=demanda.datos_suficientes, recomendaciones=lista
    )


def resumen(db: Session) -> ResumenOut:
    ahora_ = ahora()
    por_estado = {e.value: 0 for e in EstadoEquipo}
    for estado, n in db.execute(
        select(Equipo.estado, func.count()).where(Equipo.activo.is_(True)).group_by(Equipo.estado)
    ).all():
        por_estado[estado.value] = n
    por_zona = dict(
        db.execute(
            select(Zona.nombre, func.count(Equipo.id))
            .join(Equipo, Equipo.zona_id == Zona.id)
            .where(Equipo.activo.is_(True))
            .group_by(Zona.nombre)
        ).all()
    )
    return ResumenOut(
        equipos_activos=sum(por_estado.values()),
        equipos_por_estado=por_estado,
        equipos_por_zona=por_zona,
        asignaciones_en_curso=db.scalar(
            select(func.count())
            .select_from(Asignacion)
            .where(
                Asignacion.estado == EstadoAsignacion.activa,
                Asignacion.inicio <= ahora_,
                Asignacion.fin > ahora_,
            )
        ),
        incidentes_abiertos=db.scalar(
            select(func.count()).select_from(Incidente).where(Incidente.estado != EstadoIncidente.resuelto)
        ),
        mantenimientos_abiertos=db.scalar(
            select(func.count()).select_from(Mantenimiento).where(Mantenimiento.fin.is_(None))
        ),
    )
