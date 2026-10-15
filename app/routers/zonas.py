from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import requiere_roles, usuario_actual
from ..enums import Rol
from ..errors import ReglaNegocioError
from ..models import Usuario, Zona
from ..schemas import ZonaCrear, ZonaOut
from ..services import auditoria

router = APIRouter(prefix="/zonas", tags=["Inventario"])


@router.get("", response_model=list[ZonaOut])
def listar_zonas(db: Session = Depends(get_db), _: Usuario = Depends(usuario_actual)):
    return db.scalars(select(Zona).order_by(Zona.nombre)).all()


@router.post("", response_model=ZonaOut, status_code=201)
def crear_zona(
    datos: ZonaCrear,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(requiere_roles(Rol.administrador)),
):
    if db.scalar(select(Zona).where(Zona.nombre == datos.nombre)):
        raise ReglaNegocioError("Ya existe una zona con ese nombre")
    zona = Zona(nombre=datos.nombre, descripcion=datos.descripcion)
    db.add(zona)
    db.flush()
    auditoria.registrar(db, admin, "crear", "zona", zona.id, zona.nombre)
    db.commit()
    return zona
