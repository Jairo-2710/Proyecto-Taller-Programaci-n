from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ahora
from ..database import get_db
from ..deps import requiere_roles, usuario_actual
from ..enums import EstadoIncidente, Rol, Severidad
from ..errors import ReglaNegocioError
from ..models import Equipo, Incidente, Usuario
from ..schemas import IncidenteActualizar, IncidenteCrear, IncidenteOut
from ..services import auditoria
from ..services.equipos import recalcular_estado
from ..utils import obtener_o_404

router = APIRouter(prefix="/incidentes", tags=["Incidentes y mantenimiento"])
tecnicos = requiere_roles(Rol.administrador, Rol.soporte)

TRANSICIONES = {
    EstadoIncidente.abierto: {EstadoIncidente.en_atencion, EstadoIncidente.resuelto},
    EstadoIncidente.en_atencion: {EstadoIncidente.resuelto},
    EstadoIncidente.resuelto: set(),
}


@router.post("", response_model=IncidenteOut, status_code=201)
def reportar_incidente(datos: IncidenteCrear, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_actual)):
    """Cualquier usuario autenticado puede reportar una falla.

    Si la severidad es alta o crítica, el equipo pasa a 'fuera_de_servicio' hasta que se resuelva.
    """
    equipo = obtener_o_404(db, Equipo, datos.equipo_id, "Equipo no encontrado")
    incidente = Incidente(
        equipo_id=equipo.id,
        reportado_por_id=usuario.id,
        descripcion=datos.descripcion,
        severidad=datos.severidad,
    )
    db.add(incidente)
    db.flush()
    recalcular_estado(db, equipo)
    auditoria.registrar(db, usuario, "crear", "incidente", incidente.id, f"equipo={equipo.codigo}; {datos.severidad.value}")
    db.commit()
    return incidente


@router.get("", response_model=list[IncidenteOut])
def listar_incidentes(
    equipo_id: int | None = None,
    estado: EstadoIncidente | None = None,
    severidad: Severidad | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)),
):
    consulta = select(Incidente).order_by(Incidente.fecha_reporte.desc())
    if equipo_id is not None:
        consulta = consulta.where(Incidente.equipo_id == equipo_id)
    if estado is not None:
        consulta = consulta.where(Incidente.estado == estado)
    if severidad is not None:
        consulta = consulta.where(Incidente.severidad == severidad)
    return db.scalars(consulta.offset(skip).limit(limit)).all()


@router.get("/{incidente_id}", response_model=IncidenteOut)
def obtener_incidente(
    incidente_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(requiere_roles(Rol.administrador, Rol.encargado_sala, Rol.soporte, Rol.coordinador)),
):
    return obtener_o_404(db, Incidente, incidente_id, "Incidente no encontrado")


@router.patch("/{incidente_id}", response_model=IncidenteOut)
def actualizar_incidente(
    incidente_id: int,
    datos: IncidenteActualizar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(tecnicos),
):
    """Cambia el estado de atención (abierto → en_atencion → resuelto) y registra acciones y responsable."""
    incidente = obtener_o_404(db, Incidente, incidente_id, "Incidente no encontrado")
    if incidente.estado == EstadoIncidente.resuelto:
        raise ReglaNegocioError("El incidente ya está resuelto; reporte uno nuevo si la falla reaparece")

    if datos.responsable_id is not None:
        obtener_o_404(db, Usuario, datos.responsable_id, "Responsable no encontrado")
        incidente.responsable_id = datos.responsable_id
    if datos.acciones is not None:
        incidente.acciones = datos.acciones

    if datos.estado is not None and datos.estado != incidente.estado:
        if datos.estado not in TRANSICIONES[incidente.estado]:
            raise ReglaNegocioError(
                f"Transición no permitida: {incidente.estado.value} → {datos.estado.value}"
            )
        if datos.estado == EstadoIncidente.resuelto:
            if not incidente.acciones:
                raise ReglaNegocioError("Para resolver el incidente registre las acciones realizadas")
            incidente.fecha_cierre = ahora()
        incidente.estado = datos.estado
        if incidente.responsable_id is None:
            incidente.responsable_id = usuario.id

    equipo = db.get(Equipo, incidente.equipo_id)
    recalcular_estado(db, equipo)
    auditoria.registrar(db, usuario, "actualizar", "incidente", incidente.id, f"estado={incidente.estado.value}")
    db.commit()
    return incidente
