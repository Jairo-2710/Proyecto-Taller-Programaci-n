"""Dependencias de FastAPI: autenticación y control de acceso por roles."""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .enums import Rol
from .models import Usuario
from .security import decodificar_token

esquema_bearer = HTTPBearer(auto_error=False, description="Token JWT obtenido en /auth/login")


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(esquema_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    no_autenticado = HTTPException(
        status_code=401, detail="No autenticado", headers={"WWW-Authenticate": "Bearer"}
    )
    if credenciales is None:
        raise no_autenticado
    try:
        datos = decodificar_token(credenciales.credentials)
        usuario = db.get(Usuario, int(datos["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise no_autenticado
    if usuario is None or not usuario.activo:
        raise no_autenticado
    return usuario


def requiere_roles(*roles: Rol):
    """Dependencia que solo deja pasar a los roles indicados."""
    permitidos = set(roles)

    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in permitidos:
            raise HTTPException(status_code=403, detail="No tiene permisos para realizar esta operación")
        return usuario

    return verificar
