from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import usuario_actual
from ..models import Usuario
from ..schemas import LoginIn, TokenOut, UsuarioOut
from ..security import crear_token, hash_password, verificar_password

router = APIRouter(prefix="/auth", tags=["Autenticación"])

_HASH_FICTICIO = hash_password("contraseña-ficticia")  # iguala el tiempo de respuesta si el usuario no existe


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos.email.lower()))
    hash_guardado = usuario.password_hash if usuario else _HASH_FICTICIO
    valido = verificar_password(datos.password, hash_guardado)
    if usuario is None or not valido or not usuario.activo:
        raise HTTPException(status_code=401, detail="Credenciales inválidas", headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=crear_token(usuario.id, usuario.rol.value), rol=usuario.rol)


@router.get("/me", response_model=UsuarioOut)
def perfil(usuario: Usuario = Depends(usuario_actual)):
    return usuario
