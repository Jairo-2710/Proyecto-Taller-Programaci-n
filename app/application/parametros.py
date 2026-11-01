"""Parámetros de negocio inyectados en los casos de uso (la aplicación no lee variables de entorno)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ParametrosAnalisis:
    horas_operativas_dia: float = 14.0
    umbral_utilizacion_alta: float = 0.80
    umbral_utilizacion_baja: float = 0.10
    umbral_zona_baja: float = 0.30
    incidentes_para_revision: int = 3
    dias_mantenimiento_prolongado: int = 7
    min_asignaciones_analisis: int = 10
    min_dias_periodo_analisis: int = 7
