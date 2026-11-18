"""Creación de tablas y datos iniciales (administrador, zonas base y, opcionalmente, datos de demostración)."""
from ...config import (
    ADMIN_EMAIL,
    ADMIN_NOMBRE,
    ADMIN_PASSWORD,
    CARGAR_DATOS_DEMO,
    DEMO_EQUIPOS_AIO,
    DEMO_EQUIPOS_PORTATILES,
)
from ...domain.identidad.entities import Usuario
from ...domain.inventario.entities import Zona
from ...domain.shared.enums import Rol
from ..security.passwords import ScryptPasswordHasher
from . import orm  # noqa: F401  (registra las tablas en Base.metadata)
from .database import Base, SessionLocal, engine
from .demo_data import cargar_equipos, cargar_usuarios_demo, hay_equipos
from .repositories import SqlUsuarioRepository, SqlZonaRepository

ZONAS_BASE = [
    ("Sala All-in-One", "Zona con computadores All-in-One"),
    ("Sala Portátiles", "Zona con computadores portátiles"),
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        usuarios, zonas = SqlUsuarioRepository(db), SqlZonaRepository(db)
        if usuarios.contar() == 0:
            usuarios.guardar(
                Usuario(
                    nombre=ADMIN_NOMBRE,
                    email=ADMIN_EMAIL.lower(),
                    password_hash=ScryptPasswordHasher().hashear(ADMIN_PASSWORD),
                    rol=Rol.administrador,
                )
            )
        if zonas.contar() == 0:
            for nombre, descripcion in ZONAS_BASE:
                zonas.guardar(Zona(nombre=nombre, descripcion=descripcion))
        db.flush()
        if CARGAR_DATOS_DEMO:
            cargar_usuarios_demo(db)
            if not hay_equipos(db):  # solo con el inventario vacío: nunca duplica ni pisa datos reales
                cargar_equipos(db, DEMO_EQUIPOS_AIO, DEMO_EQUIPOS_PORTATILES)
        db.commit()
