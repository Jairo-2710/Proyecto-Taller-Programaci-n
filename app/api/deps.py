"""Dependencias de FastAPI: autenticación y control de acceso por roles."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..application.identidad import AuthService
from ..domain.identidad.entities import Usuario
from ..domain.shared.enums import Rol
from ..domain.shared.errors import TokenInvalidoError
from .container import get_auth_service

esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT obtenido en /auth/login")


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    auth: AuthService = Depends(get_auth_service),
) -> Usuario:
    no_autenticado = HTTPException(
        status_code=401, detail="No autenticado", headers={"WWW-Authenticate": "Bearer"}
    )
    if credenciales is None:
        raise no_autenticado
    try:
        return auth.autenticar(credenciales.credentials)
    except TokenInvalidoError:
        raise no_autenticado


def requiere_roles(*roles: Rol):
    """Dependencia que solo deja pasar a los roles indicados."""
    permitidos = set(roles)

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in permitidos:
            raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta operación")
        return usuario

    return verificar
