"""Hash de contraseñas con scrypt (librería estándar)."""
import base64
import hashlib
import hmac
import os

_N, _R, _P = 2**14, 8, 1


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode()


class ScryptPasswordHasher:
    """Implementa el puerto `PasswordHasher`."""

    def hashear(self, password: str) -> str:
        sal = os.urandom(16)
        derivada = hashlib.scrypt(password.encode(), salt=sal, n=_N, r=_R, p=_P)
        return f"scrypt${_b64(sal)}${_b64(derivada)}"

    def verificar(self, password: str, almacenado: str) -> bool:
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
