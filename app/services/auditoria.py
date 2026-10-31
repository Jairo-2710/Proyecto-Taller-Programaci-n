from sqlalchemy.orm import Session

from ..models import Auditoria, Usuario


def registrar(
    db: Session,
    usuario: Usuario | None,
    accion: str,
    entidad: str,
    entidad_id: int | None = None,
    detalle: str | None = None,
) -> None:
    """Agrega un registro de auditoría a la sesión (se confirma junto con la operación)."""
    db.add(
        Auditoria(
            usuario_id=usuario.id if usuario else None,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )
    )
