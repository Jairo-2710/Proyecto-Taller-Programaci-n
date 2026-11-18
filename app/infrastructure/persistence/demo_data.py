"""Datos de demostración: equipos de ejemplo y usuarios de prueba.

Se usan en dos sitios:
  - init_db(): al arrancar con la base de datos vacía (si CARGAR_DATOS_DEMO está activo), para
    que el sistema sea utilizable sin ejecutar ningún comando.
  - scripts/seed_demo.py: para agregar más equipos cuando se quiera.

Las cantidades reales (≈80-100 All-in-One y ≈20 portátiles) deben confirmarse en el levantamiento
de información; estos datos son solo de prueba.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...domain.identidad.entities import Usuario
from ...domain.shared.enums import Rol, TipoEquipo
from ..security.passwords import ScryptPasswordHasher
from .orm import EquipoORM, ZonaORM
from .repositories import SqlUsuarioRepository

# (nombre, correo, contraseña, rol). El administrador lo crea init_db con ADMIN_EMAIL / ADMIN_PASSWORD.
USUARIOS_DEMO = [
    ("María Gómez", "encargado1@umb.local", "Encargado123!", Rol.encargado_sala),
    ("Pedro Ramírez", "encargado2@umb.local", "Encargado123!", Rol.encargado_sala),
    ("Sofía Vargas", "estudiante@umb.local", "Estudiante123!", Rol.estudiante),
]


def cargar_usuarios_demo(db: Session) -> int:
    """Crea los usuarios de demostración que aún no existen. Devuelve cuántos creó."""
    hasher = ScryptPasswordHasher()
    usuarios = SqlUsuarioRepository(db)
    creados = 0
    for nombre, email, password, rol in USUARIOS_DEMO:
        if usuarios.por_email(email):
            continue
        usuarios.guardar(Usuario(nombre=nombre, email=email, password_hash=hasher.hashear(password), rol=rol))
        creados += 1
    return creados


def hay_equipos(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(EquipoORM)) or 0) > 0


def cargar_equipos(db: Session, aio: int, portatiles: int) -> int:
    """Crea equipos AIO-001… y PRT-001… sin repetir códigos ya existentes. Devuelve cuántos creó."""
    zonas = {z.nombre: z.id for z in db.scalars(select(ZonaORM))}
    lotes = [
        ("AIO", aio, TipoEquipo.all_in_one, zonas["Sala All-in-One"], 16, ["Python", "VS Code", "PostgreSQL"]),
        ("PRT", portatiles, TipoEquipo.portatil, zonas["Sala Portátiles"], 8, ["Python", "VS Code"]),
    ]
    creados = 0
    for prefijo, cantidad, tipo, zona_id, ram, software in lotes:
        for n in range(1, cantidad + 1):
            codigo = f"{prefijo}-{n:03d}"
            if db.scalar(select(EquipoORM.id).where(EquipoORM.codigo == codigo)):
                continue
            db.add(
                EquipoORM(
                    codigo=codigo,
                    tipo=tipo,
                    zona_id=zona_id,
                    ram_gb=ram,
                    almacenamiento_gb=512,
                    software=software,
                )
            )
            creados += 1
    return creados
