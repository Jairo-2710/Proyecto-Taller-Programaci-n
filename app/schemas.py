"""Esquemas Pydantic: validación de entrada y forma de las respuestas (OpenAPI)."""
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from .config import MAX_HORAS_ASIGNACION
from .enums import (
    EstadoAsignacion,
    EstadoEquipo,
    EstadoIncidente,
    Rol,
    Severidad,
    TipoEquipo,
    TipoMantenimiento,
)
from .utils import normalizar_fecha

FechaHora = Annotated[datetime, AfterValidator(normalizar_fecha)]
Email = Annotated[str, Field(min_length=5, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- Autenticación y usuarios
class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: Rol


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: Email
    password: str = Field(min_length=8, max_length=128)
    rol: Rol


class UsuarioActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    rol: Rol | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UsuarioOut(OrmModel):
    id: int
    nombre: str
    email: str
    rol: Rol
    activo: bool
    creado_en: datetime


# ---------------------------------------------------------------- Zonas
class ZonaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)


class ZonaOut(OrmModel):
    id: int
    nombre: str
    descripcion: str | None


# ---------------------------------------------------------------- Equipos
class EquipoCrear(BaseModel):
    codigo: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    tipo: TipoEquipo
    zona_id: int
    marca: str | None = Field(default=None, max_length=80)
    procesador: str | None = Field(default=None, max_length=120)
    ram_gb: int = Field(gt=0, le=1024)
    almacenamiento_gb: int = Field(gt=0, le=100_000)
    software: list[str] = Field(default_factory=list, max_length=50)


class EquipoActualizar(BaseModel):
    """Actualización parcial. El estado no se edita aquí: lo determinan incidentes y mantenimientos."""

    tipo: TipoEquipo | None = None
    zona_id: int | None = None
    marca: str | None = Field(default=None, max_length=80)
    procesador: str | None = Field(default=None, max_length=120)
    ram_gb: int | None = Field(default=None, gt=0, le=1024)
    almacenamiento_gb: int | None = Field(default=None, gt=0, le=100_000)
    software: list[str] | None = Field(default=None, max_length=50)


class EquipoOut(OrmModel):
    id: int
    codigo: str
    tipo: TipoEquipo
    zona_id: int
    marca: str | None
    procesador: str | None
    ram_gb: int
    almacenamiento_gb: int
    software: list[str]
    estado: EstadoEquipo
    activo: bool
    creado_en: datetime
    actualizado_en: datetime


# ---------------------------------------------------------------- Asignaciones
class Periodo(BaseModel):
    inicio: FechaHora
    fin: FechaHora

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.fin <= self.inicio:
            raise ValueError("'fin' debe ser posterior a 'inicio'")
        horas = (self.fin - self.inicio).total_seconds() / 3600
        if horas > MAX_HORAS_ASIGNACION:
            raise ValueError(f"Una asignación no puede superar {MAX_HORAS_ASIGNACION:g} horas")
        return self


class AsignacionCrear(Periodo):
    equipo_id: int
    actividad: str = Field(min_length=3, max_length=200)


class SolicitudAsignacion(Periodo):
    """Pide `cantidad` equipos para una actividad; el sistema elige los más adecuados."""

    actividad: str = Field(min_length=3, max_length=200)
    cantidad: int = Field(ge=1, le=150)
    zona_id: int | None = None
    tipo: TipoEquipo | None = None
    ram_min: int | None = Field(default=None, gt=0)
    almacenamiento_min: int | None = Field(default=None, gt=0)
    software: list[str] = Field(default_factory=list)
    permitir_otras_zonas: bool = False


class AsignacionOut(OrmModel):
    id: int
    equipo_id: int
    usuario_id: int
    actividad: str
    inicio: datetime
    fin: datetime
    estado: EstadoAsignacion
    grupo: str | None
    creado_en: datetime
    cancelada_en: datetime | None


class SugerenciaOut(BaseModel):
    solicitados: int
    disponibles_compatibles: int
    suficientes: bool
    equipos_sugeridos: list[EquipoOut]


# ---------------------------------------------------------------- Incidentes y mantenimiento
class IncidenteCrear(BaseModel):
    equipo_id: int
    descripcion: str = Field(min_length=5, max_length=2000)
    severidad: Severidad


class IncidenteActualizar(BaseModel):
    estado: EstadoIncidente | None = None
    responsable_id: int | None = None
    acciones: str | None = Field(default=None, min_length=3, max_length=2000)


class IncidenteOut(OrmModel):
    id: int
    equipo_id: int
    reportado_por_id: int
    responsable_id: int | None
    descripcion: str
    severidad: Severidad
    estado: EstadoIncidente
    acciones: str | None
    fecha_reporte: datetime
    fecha_cierre: datetime | None


class MantenimientoCrear(BaseModel):
    equipo_id: int
    tipo: TipoMantenimiento
    descripcion: str = Field(min_length=5, max_length=2000)
    incidente_id: int | None = None


class MantenimientoCerrar(BaseModel):
    acciones: str = Field(min_length=3, max_length=2000)


class MantenimientoOut(OrmModel):
    id: int
    equipo_id: int
    incidente_id: int | None
    tipo: TipoMantenimiento
    descripcion: str
    responsable_id: int
    inicio: datetime
    fin: datetime | None
    acciones: str | None
    asignaciones_afectadas: list[int] = Field(
        default_factory=list,
        description="Asignaciones activas futuras del equipo que deben reubicarse (no se cancelan solas).",
    )


class HistorialEquipoOut(BaseModel):
    equipo: EquipoOut
    asignaciones: list[AsignacionOut]
    incidentes: list[IncidenteOut]
    mantenimientos: list[MantenimientoOut]


# ---------------------------------------------------------------- Análisis y optimización
class UtilizacionEquipoOut(BaseModel):
    equipo_id: int
    codigo: str
    zona_id: int
    zona: str
    tipo: TipoEquipo
    asignaciones: int
    horas_asignadas: float
    utilizacion: float = Field(description="Horas asignadas / (días del periodo × horas operativas por día), tope 1.0")
    clasificacion: str = Field(description="alta | normal | baja")
    incidentes: int


class DemandaZonaOut(BaseModel):
    zona_id: int
    zona: str
    equipos: int
    asignaciones: int
    horas_asignadas: float
    utilizacion: float
    por_dia_semana: dict[str, float] = Field(description="Horas asignadas por día (lunes … domingo)")
    por_hora: dict[int, float] = Field(description="Horas asignadas por hora del día (0-23)")


class DemandaOut(BaseModel):
    desde: datetime
    hasta: datetime
    datos_suficientes: bool
    mensaje: str | None = None
    zonas: list[DemandaZonaOut]


class IncidentesEquipoOut(BaseModel):
    equipo_id: int
    codigo: str
    incidentes: int
    abiertos: int
    resueltos: int
    tiempo_medio_resolucion_horas: float | None


class Recomendacion(BaseModel):
    tipo: str
    prioridad: str
    mensaje: str
    zona_id: int | None = None
    equipo_ids: list[int] = Field(default_factory=list)


class RecomendacionesOut(BaseModel):
    desde: datetime
    hasta: datetime
    datos_suficientes: bool
    nota: str = (
        "Las recomendaciones son sugerencias basadas en reglas y datos históricos; "
        "no sustituyen la decisión del personal autorizado."
    )
    recomendaciones: list[Recomendacion]


class ResumenOut(BaseModel):
    equipos_activos: int
    equipos_por_estado: dict[str, int]
    equipos_por_zona: dict[str, int]
    asignaciones_en_curso: int
    incidentes_abiertos: int
    mantenimientos_abiertos: int


class AuditoriaOut(OrmModel):
    id: int
    usuario_id: int | None
    accion: str
    entidad: str
    entidad_id: int | None
    detalle: str | None
    fecha: datetime
