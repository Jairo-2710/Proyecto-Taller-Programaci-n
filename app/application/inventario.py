"""Casos de uso del contexto Inventario: zonas, equipos e historial."""
from dataclasses import dataclass

from ..domain.asignaciones.entities import Asignacion
from ..domain.asignaciones.ports import AsignacionRepository
from ..domain.identidad.entities import Usuario
from ..domain.inventario.entities import Equipo, Zona
from ..domain.inventario.ports import EquipoRepository, ZonaRepository
from ..domain.mantenimiento.entities import Incidente, Mantenimiento
from ..domain.mantenimiento.ports import IncidenteRepository, MantenimientoRepository
from ..domain.shared.enums import EstadoEquipo, TipoEquipo
from ..domain.shared.errors import NoEncontradoError, ReglaNegocioError
from ..domain.shared.ports import AuditoriaRepository, Reloj, UnitOfWork


class InventarioService:
    def __init__(
        self,
        equipos: EquipoRepository,
        zonas: ZonaRepository,
        asignaciones: AsignacionRepository,
        auditoria: AuditoriaRepository,
        uow: UnitOfWork,
        reloj: Reloj,
    ):
        self._equipos = equipos
        self._zonas = zonas
        self._asignaciones = asignaciones
        self._auditoria = auditoria
        self._uow = uow
        self._reloj = reloj

    # ---- zonas
    def listar_zonas(self) -> list[Zona]:
        return self._zonas.listar()

    def crear_zona(self, actor: Usuario, nombre: str, descripcion: str | None) -> Zona:
        if self._zonas.por_nombre(nombre):
            raise ReglaNegocioError("Ya existe una zona con ese nombre")
        zona = self._zonas.guardar(Zona(nombre=nombre, descripcion=descripcion))
        self._auditoria.registrar(actor.id, "crear", "zona", zona.id, zona.nombre)
        self._uow.commit()
        return zona

    # ---- equipos
    def crear_equipo(self, actor: Usuario, equipo: Equipo) -> Equipo:
        equipo.codigo = equipo.codigo.upper()
        if self._equipos.por_codigo(equipo.codigo):
            raise ReglaNegocioError(f"Ya existe un equipo con el código {equipo.codigo}")
        self._exigir_zona(equipo.zona_id)
        ahora = self._reloj()
        equipo.creado_en = equipo.actualizado_en = ahora
        guardado = self._equipos.guardar(equipo)
        self._auditoria.registrar(actor.id, "crear", "equipo", guardado.id, guardado.codigo)
        self._uow.commit()
        return guardado

    def listar_equipos(
        self,
        zona_id: int | None,
        tipo: TipoEquipo | None,
        estado: EstadoEquipo | None,
        activo: bool,
        skip: int,
        limit: int,
    ) -> list[Equipo]:
        return self._equipos.listar(zona_id, tipo, estado, activo, skip, limit)

    def obtener_equipo(self, equipo_id: int) -> Equipo:
        equipo = self._equipos.obtener(equipo_id)
        if equipo is None:
            raise NoEncontradoError("Equipo no encontrado")
        return equipo

    def actualizar_equipo(self, actor: Usuario, equipo_id: int, cambios: dict) -> Equipo:
        equipo = self.obtener_equipo(equipo_id)
        if cambios.get("zona_id") is not None:
            self._exigir_zona(cambios["zona_id"])
        for campo, valor in cambios.items():
            if valor is not None:
                setattr(equipo, campo, valor)
        equipo.actualizado_en = self._reloj()
        self._equipos.guardar(equipo)
        self._auditoria.registrar(actor.id, "actualizar", "equipo", equipo.id, ", ".join(cambios))
        self._uow.commit()
        return equipo

    def desactivar_equipo(self, actor: Usuario, equipo_id: int) -> Equipo:
        """Baja lógica: el equipo conserva su historial pero deja de asignarse."""
        equipo = self.obtener_equipo(equipo_id)
        pendientes = self._asignaciones.pendientes_futuras(equipo.id, self._reloj())
        if pendientes:
            raise ReglaNegocioError(
                "El equipo tiene asignaciones activas pendientes; cancélelas antes de desactivarlo",
                info={"asignaciones_pendientes": pendientes},
            )
        equipo.activo = False
        equipo.actualizado_en = self._reloj()
        self._equipos.guardar(equipo)
        self._auditoria.registrar(actor.id, "desactivar", "equipo", equipo.id, equipo.codigo)
        self._uow.commit()
        return equipo

    def _exigir_zona(self, zona_id: int) -> None:
        if self._zonas.obtener(zona_id) is None:
            raise NoEncontradoError("Zona no encontrada")


@dataclass
class HistorialEquipo:
    equipo: Equipo
    asignaciones: list[Asignacion]
    incidentes: list[Incidente]
    mantenimientos: list[Mantenimiento]


class HistorialEquipoService:
    """Trazabilidad de un equipo: lee de tres contextos (asignaciones, incidentes, mantenimientos)."""

    _TODOS = 100_000

    def __init__(
        self,
        equipos: EquipoRepository,
        asignaciones: AsignacionRepository,
        incidentes: IncidenteRepository,
        mantenimientos: MantenimientoRepository,
    ):
        self._equipos = equipos
        self._asignaciones = asignaciones
        self._incidentes = incidentes
        self._mantenimientos = mantenimientos

    def obtener(self, equipo_id: int) -> HistorialEquipo:
        equipo = self._equipos.obtener(equipo_id)
        if equipo is None:
            raise NoEncontradoError("Equipo no encontrado")
        n = self._TODOS
        return HistorialEquipo(
            equipo=equipo,
            asignaciones=list(reversed(self._asignaciones.listar(equipo_id, None, None, None, 0, n))),
            incidentes=list(reversed(self._incidentes.listar(equipo_id, None, None, 0, n))),
            mantenimientos=list(reversed(self._mantenimientos.listar(equipo_id, None, 0, n))),
        )
