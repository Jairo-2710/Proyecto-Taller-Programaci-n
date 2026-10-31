"""Hash de contraseñas (scrypt, librería estándar) y tokens JWT."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, SECRET_KEY

_N, _R, _P = 2**14, 8, 1


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode()


def hash_password(password: str) -> str:
    sal = os.urandom(16)
    derivada = hashlib.scrypt(password.encode(), salt=sal, n=_N, r=_R, p=_P)
    return f"scrypt${_b64(sal)}${_b64(derivada)}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        esquema, sal_b64, hash_b64 = almacenado.split("$")
        if esquema != "scrypt":
            return False
        sal = base64.b64decode(sal_b64)
        esperado = base64.b64decode(hash_b64)
        obtenido = hashlib.scrypt(password.encode(), salt=sal, n=_N, r=_R, p=_P)
        return hmac.compare_digest(obtenido, esperado)
    except (ValueError, TypeError):
        return False


def crear_token(usuario_id: int, rol: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": str(usuario_id), "rol": rol, "exp": expira}, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si el token es inválido o expiró."""
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
