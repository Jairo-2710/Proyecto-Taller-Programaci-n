"""Modelo de datos relacional (SQLAlchemy 2.0)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import ahora
from .database import Base
from .enums import (
    EstadoAsignacion,
    EstadoEquipo,
    EstadoIncidente,
    Rol,
    Severidad,
    TipoEquipo,
    TipoMantenimiento,
)


def _enum(tipo):
    return SAEnum(
        tipo,
        native_enum=False,
        length=30,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[Rol] = mapped_column(_enum(Rol))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Zona(Base):
    __tablename__ = "zonas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255))


class Equipo(Base):
    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    tipo: Mapped[TipoEquipo] = mapped_column(_enum(TipoEquipo))
    zona_id: Mapped[int] = mapped_column(ForeignKey("zonas.id"), index=True)
    marca: Mapped[str | None] = mapped_column(String(80))
    procesador: Mapped[str | None] = mapped_column(String(120))
    ram_gb: Mapped[int]
    almacenamiento_gb: Mapped[int]
    software: Mapped[list] = mapped_column(JSON, default=list)
    estado: Mapped[EstadoEquipo] = mapped_column(_enum(EstadoEquipo), default=EstadoEquipo.disponible)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    zona: Mapped[Zona] = relationship(lazy="joined")


class Asignacion(Base):
    __tablename__ = "asignaciones"
    __table_args__ = (Index("ix_asignacion_equipo_periodo", "equipo_id", "inicio", "fin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    actividad: Mapped[str] = mapped_column(String(200))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime] = mapped_column(DateTime)
    estado: Mapped[EstadoAsignacion] = mapped_column(_enum(EstadoAsignacion), default=EstadoAsignacion.activa)
    grupo: Mapped[str | None] = mapped_column(String(36), index=True)  # une las asignaciones de una misma solicitud
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime)


class Incidente(Base):
    __tablename__ = "incidentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), index=True)
    reportado_por_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    responsable_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    descripcion: Mapped[str] = mapped_column(Text)
    severidad: Mapped[Severidad] = mapped_column(_enum(Severidad))
    estado: Mapped[EstadoIncidente] = mapped_column(_enum(EstadoIncidente), default=EstadoIncidente.abierto)
    acciones: Mapped[str | None] = mapped_column(Text)
    fecha_reporte: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime)


class Mantenimiento(Base):
    __tablename__ = "mantenimientos"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), index=True)
    incidente_id: Mapped[int | None] = mapped_column(ForeignKey("incidentes.id"))
    tipo: Mapped[TipoMantenimiento] = mapped_column(_enum(TipoMantenimiento))
    descripcion: Mapped[str] = mapped_column(Text)
    responsable_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    inicio: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fin: Mapped[datetime | None] = mapped_column(DateTime)  # None = mantenimiento abierto
    acciones: Mapped[str | None] = mapped_column(Text)


class Auditoria(Base):
    """Registro de operaciones importantes (trazabilidad)."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str] = mapped_column(String(40))
    entidad_id: Mapped[int | None]
    detalle: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
