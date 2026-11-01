"""Creación de tablas y datos iniciales (administrador y zonas base)."""
from ...config import ADMIN_EMAIL, ADMIN_NOMBRE, ADMIN_PASSWORD
from ...domain.identidad.entities import Usuario
from ...domain.inventario.entities import Zona
from ...domain.shared.enums import Rol
from ..security.passwords import ScryptPasswordHasher
from . import orm  # noqa: F401  (registra las tablas en Base.metadata)
from .database import Base, SessionLocal, engine
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
        db.commit()
