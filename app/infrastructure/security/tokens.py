"""Tokens JWT."""
from datetime import datetime, timedelta, timezone

import jwt

from ...domain.shared.errors import TokenInvalidoError


class JwtTokenService:
    """Implementa el puerto `TokenService`."""

    def __init__(self, secret_key: str, algoritmo: str = "HS256", minutos: int = 60):
        self._secret = secret_key
        self._algoritmo = algoritmo
        self._minutos = minutos

    def crear(self, usuario_id: int, rol: str) -> str:
        expira = datetime.now(timezone.utc) + timedelta(minutes=self._minutos)
        return jwt.encode({"sub": str(usuario_id), "rol": rol, "exp": expira}, self._secret, algorithm=self._algoritmo)

    def decodificar(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algoritmo])
        except jwt.PyJWTError:
            raise TokenInvalidoError("No autenticado")
