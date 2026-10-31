"""Creación de tablas y datos iniciales (administrador y zonas base)."""
from sqlalchemy import func, select

from . import models  # noqa: F401  (registra las tablas en Base.metadata)
from .config import ADMIN_EMAIL, ADMIN_NOMBRE, ADMIN_PASSWORD
from .database import Base, SessionLocal, engine
from .enums import Rol
from .models import Usuario, Zona
from .security import hash_password

ZONAS_BASE = [
    ("Sala All-in-One", "Zona con computadores All-in-One"),
    ("Sala Portátiles", "Zona con computadores portátiles"),
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Usuario)) == 0:
            db.add(
                Usuario(
                    nombre=ADMIN_NOMBRE,
                    email=ADMIN_EMAIL.lower(),
                    password_hash=hash_password(ADMIN_PASSWORD),
                    rol=Rol.administrador,
                )
            )
        if db.scalar(select(func.count()).select_from(Zona)) == 0:
            db.add_all(Zona(nombre=n, descripcion=d) for n, d in ZONAS_BASE)
        db.commit()
