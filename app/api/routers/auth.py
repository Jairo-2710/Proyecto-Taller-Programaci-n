from fastapi import APIRouter, Depends

from ...application.identidad import AuthService
from ...domain.identidad.entities import Usuario
from ..container import get_auth_service
from ..deps import usuario_actual
from ..schemas import LoginIn, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, auth: AuthService = Depends(get_auth_service)):
    token, rol = auth.login(datos.email, datos.password)
    return TokenOut(access_token=token, rol=rol)


@router.get("/me", response_model=UsuarioOut)
def perfil(usuario: Usuario = Depends(usuario_actual)):
    return usuario
