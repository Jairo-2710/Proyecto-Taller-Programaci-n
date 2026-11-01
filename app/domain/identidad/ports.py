from typing import Protocol

from .entities import Usuario


class UsuarioRepository(Protocol):
    def obtener(self, usuario_id: int) -> Usuario | None: ...

    def por_email(self, email: str) -> Usuario | None: ...

    def listar(self, skip: int, limit: int) -> list[Usuario]: ...

    def contar(self) -> int: ...

    def guardar(self, usuario: Usuario) -> Usuario:
        """Inserta (si `id` es None) o actualiza. Devuelve la entidad con su id asignado."""


class PasswordHasher(Protocol):
    def hashear(self, password: str) -> str: ...

    def verificar(self, password: str, almacenado: str) -> bool: ...


class TokenService(Protocol):
    def crear(self, usuario_id: int, rol: str) -> str: ...

    def decodificar(self, token: str) -> dict:
        """Devuelve el contenido del token. Lanza TokenInvalidoError si no es válido."""
