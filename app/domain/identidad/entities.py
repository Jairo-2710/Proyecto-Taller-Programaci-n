from dataclasses import dataclass
from datetime import datetime

from ..shared.enums import Rol


@dataclass
class Usuario:
    nombre: str
    email: str
    password_hash: str
    rol: Rol
    activo: bool = True
    creado_en: datetime | None = None
    id: int | None = None
