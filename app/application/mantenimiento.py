"""Casos de uso del contexto Mantenimiento: incidentes y mantenimientos."""
from ..domain.asignaciones.ports import AsignacionRepository
from ..domain.identidad.entities import Usuario
from ..domain.identidad.ports import UsuarioRepository
from ..domain.inventario.entities import Equipo
from ..domain.inventario.ports import EquipoRepository
from ..domain.mantenimiento import policies
from ..domain.mantenimiento.entities import Incidente, Mantenimiento, ResultadoMantenimiento
from ..domain.mantenimiento.ports import IncidenteRepository, MantenimientoRepository
from ..domain.shared.enums import EstadoIncidente, Severidad, TipoMantenimiento
from ..domain.shared.errors import NoEncontradoError, ReglaNegocioError
from ..domain.shared.ports import AuditoriaRepository, Reloj, UnitOfWork


class EstadoEquipoService:
    """Mantiene el estado operativo del equipo coherente con sus incidentes y mantenimientos."""

    def __init__(
        self,
        equipos: EquipoRepository,
        mantenimientos: MantenimientoRepository,
        incidentes: IncidenteRepository,
        reloj: Reloj,
    ):
        self._equipos = equipos
        self._mantenimientos = mantenimientos
        self._incidentes = incidentes
        self._reloj = reloj

    def recalcular(self, equipo: Equipo) -> None:
        nuevo = policies.derivar_estado(
            self._mantenimientos.contar_abiertos_de_equipo(equipo.id),
            self._incidentes.contar_graves_abiertos(equipo.id),
        )
        if equipo.estado != nuevo:
            equipo.estado = nuevo
            equipo.actualizado_en = self._reloj()
            self._equipos.guardar(equipo)


class IncidenteService:
    def __init__(
        self,
        incidentes: IncidenteRepository,
        equipos: EquipoRepository,
        usuarios: UsuarioRepository,
        estado_equipo: EstadoEquipoService,
        auditoria: AuditoriaRepository,
        uow: UnitOfWork,
        reloj: Reloj,
    ):
        self._incidentes = incidentes
        self._equipos = equipos
        self._usuarios = usuarios
        self._estado_equipo = estado_equipo
        self._auditoria = auditoria
        self._uow = uow
        self._reloj = reloj

    def reportar(self, actor: Usuario, equipo_id: int, descripcion: str, severidad: Severidad) -> Incidente:
        """Una severidad alta o crítica deja el equipo fuera de servicio hasta que se resuelva."""
        equipo = self._equipos.obtener(equipo_id)
        if equipo is None:
            raise NoEncontradoError("Equipo no encontrado")
        incidente = self._incidentes.guardar(
            Incidente(
                equipo_id=equipo.id,
                reportado_por_id=actor.id,
                descripcion=descripcion,
                severidad=severidad,
                fecha_reporte=self._reloj(),
            )
        )
        self._estado_equipo.recalcular(equipo)
        self._auditoria.registrar(
            actor.id, "crear", "incidente", incidente.id, f"equipo={equipo.codigo}; {severidad.value}"
        )
        self._uow.commit()
        return incidente

    def listar(
        self,
        equipo_id: int | None,
        estado: EstadoIncidente | None,
        severidad: Severidad | None,
        skip: int,
        limit: int,
    ) -> list[Incidente]:
        return self._incidentes.listar(equipo_id, estado, severidad, skip, limit)

    def obtener(self, incidente_id: int) -> Incidente:
        incidente = self._incidentes.obtener(incidente_id)
        if incidente is None:
            raise NoEncontradoError("Incidente no encontrado")
        return incidente

    def actualizar(
        self,
        actor: Usuario,
        incidente_id: int,
        estado: EstadoIncidente | None,
        responsable_id: int | None,
        acciones: str | None,
    ) -> Incidente:
        """abierto → en_atencion → resuelto. Para resolver deben registrarse las acciones realizadas."""
        incidente = self.obtener(incidente_id)
        if incidente.estado == EstadoIncidente.resuelto:
            raise ReglaNegocioError("El incidente ya está resuelto; reporte uno nuevo si la falla reaparece")
        if responsable_id is not None and self._usuarios.obtener(responsable_id) is None:
            raise NoEncontradoError("Responsable no encontrado")

        if responsable_id is not None:
            incidente.responsable_id = responsable_id
        if acciones is not None:
            incidente.acciones = acciones
        if estado is not None and estado != incidente.estado:
            policies.validar_transicion(incidente.estado, estado)
            if estado == EstadoIncidente.resuelto:
                if not incidente.acciones:
                    raise ReglaNegocioError("Para resolver el incidente registre las acciones realizadas")
                incidente.fecha_cierre = self._reloj()
            incidente.estado = estado
            if incidente.responsable_id is None:
                incidente.responsable_id = actor.id

        self._incidentes.guardar(incidente)
        equipo = self._equipos.obtener(incidente.equipo_id)
        self._estado_equipo.recalcular(equipo)
        self._auditoria.registrar(actor.id, "actualizar", "incidente", incidente.id, f"estado={incidente.estado.value}")
        self._uow.commit()
        return incidente


class MantenimientoService:
    def __init__(
        self,
        mantenimientos: MantenimientoRepository,
        incidentes: IncidenteRepository,
        equipos: EquipoRepository,
        asignaciones: AsignacionRepository,
        estado_equipo: EstadoEquipoService,
        auditoria: AuditoriaRepository,
        uow: UnitOfWork,
        reloj: Reloj,
    ):
        self._mantenimientos = mantenimientos
        self._incidentes = incidentes
        self._equipos = equipos
        self._asignaciones = asignaciones
        self._estado_equipo = estado_equipo
        self._auditoria = auditoria
        self._uow = uow
        self._reloj = reloj

    def iniciar(
        self,
        actor: Usuario,
        equipo_id: int,
        tipo: TipoMantenimiento,
        descripcion: str,
        incidente_id: int | None,
    ) -> ResultadoMantenimiento:
        """Abre un mantenimiento: el equipo pasa a 'en_mantenimiento' y deja de asignarse."""
        equipo = self._equipos.obtener(equipo_id)
        if equipo is None:
            raise NoEncontradoError("Equipo no encontrado")
        if not equipo.activo:
            raise ReglaNegocioError("El equipo está desactivado")
        if self._mantenimientos.contar_abiertos_de_equipo(equipo.id):
            raise ReglaNegocioError(f"El equipo {equipo.codigo} ya tiene un mantenimiento abierto")
        if incidente_id is not None:
            incidente = self._incidentes.obtener(incidente_id)
            if incidente is None:
                raise NoEncontradoError("Incidente no encontrado")
            if incidente.equipo_id != equipo.id:
                raise ReglaNegocioError("El incidente pertenece a otro equipo")

        ahora = self._reloj()
        mantenimiento = self._mantenimientos.guardar(
            Mantenimiento(
                equipo_id=equipo.id,
                incidente_id=incidente_id,
                tipo=tipo,
                descripcion=descripcion,
                responsable_id=actor.id,
                inicio=ahora,
            )
        )
        self._estado_equipo.recalcular(equipo)
        # No se cancelan solas: se avisa para que el personal las reubique.
        afectadas = self._asignaciones.pendientes_futuras(equipo.id, ahora)
        self._auditoria.registrar(actor.id, "iniciar", "mantenimiento", mantenimiento.id, f"equipo={equipo.codigo}")
        self._uow.commit()
        return ResultadoMantenimiento(mantenimiento, afectadas)

    def cerrar(self, actor: Usuario, mantenimiento_id: int, acciones: str) -> Mantenimiento:
        mantenimiento = self._mantenimientos.obtener(mantenimiento_id)
        if mantenimiento is None:
            raise NoEncontradoError("Mantenimiento no encontrado")
        if mantenimiento.fin is not None:
            raise ReglaNegocioError("El mantenimiento ya estaba cerrado")
        mantenimiento.fin = self._reloj()
        mantenimiento.acciones = acciones
        self._mantenimientos.guardar(mantenimiento)
        equipo = self._equipos.obtener(mantenimiento.equipo_id)
        self._estado_equipo.recalcular(equipo)
        self._auditoria.registrar(actor.id, "cerrar", "mantenimiento", mantenimiento.id, f"equipo={equipo.codigo}")
        self._uow.commit()
        return mantenimiento

    def listar(self, equipo_id: int | None, abiertos: bool | None, skip: int, limit: int) -> list[Mantenimiento]:
        return self._mantenimientos.listar(equipo_id, abiertos, skip, limit)
