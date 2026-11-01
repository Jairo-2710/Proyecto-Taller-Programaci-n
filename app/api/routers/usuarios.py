from fastapi import APIRouter, Depends, Query

from ...application.identidad import AuditoriaService, UsuarioService
from ...domain.identidad.entities import Usuario
from ...domain.shared.enums import Rol
from ..container import get_auditoria_service, get_usuario_service
from ..deps import requiere_roles
from ..schemas import AuditoriaOut, UsuarioActualizar, UsuarioCrear, UsuarioOut

router = APIRouter(prefix="/usuarios", tags=["Usuarios y roles"])
router_auditoria = APIRouter(prefix="/auditoria", tags=["Usuarios y roles"])
solo_admin = requiere_roles(Rol.administrador)


@router.post("", response_model=UsuarioOut, status_code=201)
def crear_usuario(
    datos: UsuarioCrear, servicio: UsuarioService = Depends(get_usuario_service), admin: Usuario = Depends(solo_admin)
):
    return servicio.crear(admin, datos.nombre, datos.email, datos.password, datos.rol)


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    servicio: UsuarioService = Depends(get_usuario_service),
    _: Usuario = Depends(solo_admin),
):
    return servicio.listar(skip, limit)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioActualizar,
    servicio: UsuarioService = Depends(get_usuario_service),
    admin: Usuario = Depends(solo_admin),
):
    return servicio.actualizar(admin, usuario_id, datos.model_dump(exclude_unset=True))


@router_auditoria.get("", response_model=list[AuditoriaOut])
def listar_auditoria(
    entidad: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    servicio: AuditoriaService = Depends(get_auditoria_service),
    _: Usuario = Depends(solo_admin),
):
    """Registro de operaciones importantes (trazabilidad)."""
    return servicio.listar(entidad, skip, limit)
