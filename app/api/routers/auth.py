from fastapi import APIRouter, Depends, HTTPException, Request

from ...application.identidad import AuthService
from ...domain.identidad.entities import Usuario
from ...domain.shared.errors import CredencialesInvalidasError
from ..container import get_auth_service
from ..deps import usuario_actual
from ..rate_limit import login_limiter
from ..schemas import LoginIn, TokenOut, UsuarioOut

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=TokenOut)
def login(
    datos: LoginIn,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    client_ip = request.client.host if request.client else "unknown"
    key = (client_ip, datos.email.strip().lower())

    retry_after = login_limiter.check(key)

    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        token, rol = auth.login(datos.email, datos.password)
    except CredencialesInvalidasError:
        login_limiter.record_failure(key)
        raise

    login_limiter.reset(key)

    return TokenOut(access_token=token, rol=rol)


@router.get("/me", response_model=UsuarioOut)
def perfil(usuario: Usuario = Depends(usuario_actual)):
    return usuario
