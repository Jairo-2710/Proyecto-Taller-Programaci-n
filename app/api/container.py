"""Punto de composición (composition root): único lugar donde se eligen las implementaciones.

Aquí se conectan los puertos del dominio con sus adaptadores y se construyen los casos de uso
inyectando cada dependencia por constructor. Las pruebas pueden reemplazar cualquier proveedor con
`app.dependency_overrides[proveedor] = ...`.
"""
import time
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from .. import config
from ..application.analisis import AnalisisService
from ..application.analitica import DatosAbiertosService, EstadisticasService
from ..application.asignaciones import AsignacionService
from ..application.identidad import AuditoriaService, AuthService, UsuarioService
from ..application.inventario import HistorialEquipoService, InventarioService
from ..application.mantenimiento import EstadoEquipoService, IncidenteService, MantenimientoService
from ..application.parametros import ParametrosAnalisis
from ..infrastructure.analytics.duckdb_motor import DuckDbMotor
from ..infrastructure.opendata.fuentes import DaneAdapter, DatosGovCoAdapter
from ..infrastructure.opendata.transport import ErrorTransitorio, TransporteUrllib
from ..infrastructure.persistence.database import SessionLocal
from ..infrastructure.persistence.repositories import (
    SqlAsignacionRepository,
    SqlAuditoriaRepository,
    SqlEquipoRepository,
    SqlIncidenteRepository,
    SqlMantenimientoRepository,
    SqlUnitOfWork,
    SqlUsuarioRepository,
    SqlZonaRepository,
)
from ..infrastructure.resilience.circuit_breaker import CircuitBreaker
from ..infrastructure.security.passwords import ScryptPasswordHasher
from ..infrastructure.security.tokens import JwtTokenService

reloj = config.ahora


# ---------------------------------------------------------------- persistencia (una sesión por petición)
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@dataclass
class Repositorios:
    usuarios: SqlUsuarioRepository
    zonas: SqlZonaRepository
    equipos: SqlEquipoRepository
    asignaciones: SqlAsignacionRepository
    incidentes: SqlIncidenteRepository
    mantenimientos: SqlMantenimientoRepository
    auditoria: SqlAuditoriaRepository
    uow: SqlUnitOfWork


def get_repositorios(session: Session = Depends(get_session)) -> Repositorios:
    return Repositorios(
        usuarios=SqlUsuarioRepository(session),
        zonas=SqlZonaRepository(session),
        equipos=SqlEquipoRepository(session),
        asignaciones=SqlAsignacionRepository(session),
        incidentes=SqlIncidenteRepository(session),
        mantenimientos=SqlMantenimientoRepository(session),
        auditoria=SqlAuditoriaRepository(session),
        uow=SqlUnitOfWork(session),
    )


# ---------------------------------------------------------------- servicios sin estado (singletons)
@lru_cache
def get_hasher() -> ScryptPasswordHasher:
    return ScryptPasswordHasher()


@lru_cache
def get_tokens() -> JwtTokenService:
    return JwtTokenService(config.SECRET_KEY, config.JWT_ALGORITHM, config.ACCESS_TOKEN_MINUTES)


@lru_cache
def get_motor_analitico() -> DuckDbMotor:
    return DuckDbMotor()


def get_parametros_analisis() -> ParametrosAnalisis:
    return ParametrosAnalisis(
        horas_operativas_dia=config.HORAS_OPERATIVAS_DIA,
        umbral_utilizacion_alta=config.UMBRAL_UTILIZACION_ALTA,
        umbral_utilizacion_baja=config.UMBRAL_UTILIZACION_BAJA,
        umbral_zona_baja=config.UMBRAL_ZONA_BAJA,
        incidentes_para_revision=config.INCIDENTES_PARA_REVISION,
        dias_mantenimiento_prolongado=config.DIAS_MANTENIMIENTO_PROLONGADO,
        min_asignaciones_analisis=config.MIN_ASIGNACIONES_ANALISIS,
        min_dias_periodo_analisis=config.MIN_DIAS_PERIODO_ANALISIS,
    )


# ---------------------------------------------------------------- APIs públicas (con estado: el breaker debe persistir)
def _crear_breaker(nombre: str) -> CircuitBreaker:
    return CircuitBreaker(
        nombre,
        umbral_fallos=config.BREAKER_UMBRAL_FALLOS,
        tiempo_recuperacion_s=config.BREAKER_RECUPERACION_S,
        reloj=time.monotonic,
        excepciones_que_cuentan=(ErrorTransitorio,),
    )


@lru_cache
def get_fuente_datos_gov():
    return DatosGovCoAdapter(
        base_url=config.DATOS_GOV_BASE_URL,
        dataset_id=config.DATOS_GOV_DATASET_ID,
        transporte=TransporteUrllib(),
        breaker=_crear_breaker("datos.gov.co"),
        reloj=reloj,
        intentos=config.RETRY_INTENTOS,
        base_s=config.RETRY_BASE_S,
        timeout_s=config.OPENDATA_TIMEOUT_S,
        app_token=config.SOCRATA_APP_TOKEN,
    )


@lru_cache
def get_fuente_dane():
    return DaneAdapter(
        base_url=config.DANE_BASE_URL,
        dataset_id=config.DANE_DATASET_ID,
        transporte=TransporteUrllib(),
        breaker=_crear_breaker("DANE"),
        reloj=reloj,
        intentos=config.RETRY_INTENTOS,
        base_s=config.RETRY_BASE_S,
        timeout_s=config.OPENDATA_TIMEOUT_S,
        app_token=config.SOCRATA_APP_TOKEN,
    )


# ---------------------------------------------------------------- casos de uso (DI por constructor)
def get_auth_service(r: Repositorios = Depends(get_repositorios), hasher=Depends(get_hasher), tokens=Depends(get_tokens)):
    return AuthService(usuarios=r.usuarios, hasher=hasher, tokens=tokens)


def get_usuario_service(r: Repositorios = Depends(get_repositorios), hasher=Depends(get_hasher)):
    return UsuarioService(usuarios=r.usuarios, hasher=hasher, auditoria=r.auditoria, uow=r.uow)


def get_auditoria_service(r: Repositorios = Depends(get_repositorios)):
    return AuditoriaService(auditoria=r.auditoria)


def get_inventario_service(r: Repositorios = Depends(get_repositorios)):
    return InventarioService(
        equipos=r.equipos, zonas=r.zonas, asignaciones=r.asignaciones, auditoria=r.auditoria, uow=r.uow, reloj=reloj
    )


def get_historial_service(r: Repositorios = Depends(get_repositorios)):
    return HistorialEquipoService(
        equipos=r.equipos, asignaciones=r.asignaciones, incidentes=r.incidentes, mantenimientos=r.mantenimientos
    )


def get_asignacion_service(r: Repositorios = Depends(get_repositorios)):
    return AsignacionService(
        equipos=r.equipos,
        asignaciones=r.asignaciones,
        mantenimientos=r.mantenimientos,
        auditoria=r.auditoria,
        uow=r.uow,
        reloj=reloj,
        max_horas_asignacion=config.MAX_HORAS_ASIGNACION,
    )


def get_estado_equipo_service(r: Repositorios = Depends(get_repositorios)):
    return EstadoEquipoService(equipos=r.equipos, mantenimientos=r.mantenimientos, incidentes=r.incidentes, reloj=reloj)


def get_incidente_service(
    r: Repositorios = Depends(get_repositorios), estado_equipo=Depends(get_estado_equipo_service)
):
    return IncidenteService(
        incidentes=r.incidentes,
        equipos=r.equipos,
        usuarios=r.usuarios,
        estado_equipo=estado_equipo,
        auditoria=r.auditoria,
        uow=r.uow,
        reloj=reloj,
    )


def get_mantenimiento_service(
    r: Repositorios = Depends(get_repositorios), estado_equipo=Depends(get_estado_equipo_service)
):
    return MantenimientoService(
        mantenimientos=r.mantenimientos,
        incidentes=r.incidentes,
        equipos=r.equipos,
        asignaciones=r.asignaciones,
        estado_equipo=estado_equipo,
        auditoria=r.auditoria,
        uow=r.uow,
        reloj=reloj,
    )


def get_analisis_service(r: Repositorios = Depends(get_repositorios), parametros=Depends(get_parametros_analisis)):
    return AnalisisService(
        equipos=r.equipos,
        zonas=r.zonas,
        asignaciones=r.asignaciones,
        incidentes=r.incidentes,
        mantenimientos=r.mantenimientos,
        reloj=reloj,
        parametros=parametros,
    )


def get_estadisticas_service(r: Repositorios = Depends(get_repositorios), motor=Depends(get_motor_analitico)):
    return EstadisticasService(equipos=r.equipos, zonas=r.zonas, asignaciones=r.asignaciones, motor=motor)


def get_datos_abiertos_service(
    datos_gov=Depends(get_fuente_datos_gov), dane=Depends(get_fuente_dane), motor=Depends(get_motor_analitico)
):
    return DatosAbiertosService(
        datos_gov_co=datos_gov,
        dane=dane,
        motor=motor,
        reloj=reloj,
        limite_registros=config.OPENDATA_LIMITE_REGISTROS,
    )
