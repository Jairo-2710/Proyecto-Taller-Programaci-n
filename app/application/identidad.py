"""Casos de uso del contexto Identidad: autenticación, usuarios y auditoría."""
from ..domain.identidad.entities import Usuario
from ..domain.identidad.ports import PasswordHasher, TokenService, UsuarioRepository
from ..domain.shared.enums import Rol
from ..domain.shared.errors import (
    CredencialesInvalidasError,
    NoEncontradoError,
    ReglaNegocioError,
    TokenInvalidoError,
)
from ..domain.shared.ports import AuditoriaRepository, RegistroAuditoria, UnitOfWork


class AuthService:
    _hash_ficticio: str | None = None

    def __init__(self, usuarios: UsuarioRepository, hasher: PasswordHasher, tokens: TokenService):
        self._usuarios = usuarios
        self._hasher = hasher
        self._tokens = tokens

    def login(self, email: str, password: str) -> tuple[str, Rol]:
        usuario = self._usuarios.por_email(email.lower())
        # Si el usuario no existe se verifica contra un hash ficticio para igualar el tiempo de respuesta.
        if AuthService._hash_ficticio is None:
            AuthService._hash_ficticio = self._hasher.hashear("contraseña-ficticia")
        almacenado = usuario.password_hash if usuario else AuthService._hash_ficticio
        valido = self._hasher.verificar(password, almacenado)
        if usuario is None or not valido or not usuario.activo:
            raise CredencialesInvalidasError("Credenciales inválidas")
        return self._tokens.crear(usuario.id, usuario.rol.value), usuario.rol

    def autenticar(self, token: str) -> Usuario:
        datos = self._tokens.decodificar(token)
        try:
            usuario = self._usuarios.obtener(int(datos["sub"]))
        except (KeyError, ValueError):
            raise TokenInvalidoError("No autenticado")
        if usuario is None or not usuario.activo:
            raise TokenInvalidoError("No autenticado")
        return usuario


class UsuarioService:
    def __init__(
        self,
        usuarios: UsuarioRepository,
        hasher: PasswordHasher,
        auditoria: AuditoriaRepository,
        uow: UnitOfWork,
    ):
        self._usuarios = usuarios
        self._hasher = hasher
        self._auditoria = auditoria
        self._uow = uow

    def crear(self, actor: Usuario, nombre: str, email: str, password: str, rol: Rol) -> Usuario:
        email = email.lower()
        if self._usuarios.por_email(email):
            raise ReglaNegocioError("Ya existe un usuario con ese correo")
        usuario = self._usuarios.guardar(
            Usuario(nombre=nombre, email=email, password_hash=self._hasher.hashear(password), rol=rol)
        )
        self._auditoria.registrar(actor.id, "crear", "usuario", usuario.id, f"rol={usuario.rol.value}")
        self._uow.commit()
        return usuario

    def listar(self, skip: int, limit: int) -> list[Usuario]:
        return self._usuarios.listar(skip, limit)

    def actualizar(self, actor: Usuario, usuario_id: int, cambios: dict) -> Usuario:
        usuario = self._usuarios.obtener(usuario_id)
        if usuario is None:
            raise NoEncontradoError("Usuario no encontrado")
        se_quita_admin = cambios.get("activo") is False or ("rol" in cambios and cambios["rol"] != Rol.administrador)
        if usuario.id == actor.id and se_quita_admin:
            raise ReglaNegocioError("No puede desactivarse ni quitarse el rol de administrador a sí mismo")
        campos = ", ".join(cambios)
        cambios = dict(cambios)
        if "password" in cambios:
            usuario.password_hash = self._hasher.hashear(cambios.pop("password"))
        for campo, valor in cambios.items():
            setattr(usuario, campo, valor)
        self._usuarios.guardar(usuario)
        self._auditoria.registrar(actor.id, "actualizar", "usuario", usuario.id, campos)
        self._uow.commit()
        return usuario


class AuditoriaService:
    def __init__(self, auditoria: AuditoriaRepository):
        self._auditoria = auditoria

    def listar(self, entidad: str | None, skip: int, limit: int) -> list[RegistroAuditoria]:
        return self._auditoria.listar(entidad, skip, limit)
