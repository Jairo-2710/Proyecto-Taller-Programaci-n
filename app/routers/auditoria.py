from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import requiere_roles
from ..enums import Rol
from ..models import Auditoria, Usuario
from ..schemas import AuditoriaOut

router = APIRouter(prefix="/auditoria", tags=["Usuarios y roles"])


@router.get("", response_model=list[AuditoriaOut])
def listar_auditoria(
    entidad: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_roles(Rol.administrador)),
):
    """Registro de operaciones importantes (trazabilidad)."""
    consulta = select(Auditoria).order_by(Auditoria.id.desc())
    if entidad:
        consulta = consulta.where(Auditoria.entidad == entidad)
    return db.scalars(consulta.offset(skip).limit(limit)).all()
