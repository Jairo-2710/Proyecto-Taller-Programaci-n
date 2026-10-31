from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import requiere_roles
from ..enums import Rol
from ..errors import ReglaNegocioError
from ..models import Usuario
from ..schemas import UsuarioActualizar, UsuarioCrear, UsuarioOut
from ..security import hash_password
from ..services import auditoria
from ..utils import obtener_o_404

router = APIRouter(prefix="/usuarios", tags=["Usuarios y roles"])
solo_admin = requiere_roles(Rol.administrador)


@router.post("", response_model=UsuarioOut, status_code=201)
def crear_usuario(datos: UsuarioCrear, db: Session = Depends(get_db), admin: Usuario = Depends(solo_admin)):
    email = datos.email.lower()
    if db.scalar(select(Usuario).where(Usuario.email == email)):
        raise ReglaNegocioError("Ya existe un usuario con ese correo")
    usuario = Usuario(nombre=datos.nombre, email=email, password_hash=hash_password(datos.password), rol=datos.rol)
    db.add(usuario)
    db.flush()
    auditoria.registrar(db, admin, "crear", "usuario", usuario.id, f"rol={usuario.rol.value}")
    db.commit()
    return usuario


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_admin),
):
    return db.scalars(select(Usuario).order_by(Usuario.id).offset(skip).limit(limit)).all()


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(solo_admin),
):
    usuario = obtener_o_404(db, Usuario, usuario_id, "Usuario no encontrado")
    cambios = datos.model_dump(exclude_unset=True)
    if usuario.id == admin.id and (cambios.get("activo") is False or ("rol" in cambios and cambios["rol"] != Rol.administrador)):
        raise ReglaNegocioError("No puede desactivarse ni quitarse el rol de administrador a sí mismo")
    if "password" in cambios:
        usuario.password_hash = hash_password(cambios.pop("password"))
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)
    auditoria.registrar(db, admin, "actualizar", "usuario", usuario.id, ", ".join(datos.model_dump(exclude_unset=True)))
    db.commit()
    return usuario
