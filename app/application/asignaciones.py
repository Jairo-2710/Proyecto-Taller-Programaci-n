"""Casos de uso del contexto Asignaciones: disponibilidad, asignación y cancelación."""
import uuid
from datetime import datetime

from ..domain.asignaciones import policies
from ..domain.asignaciones.entities import (
    Asignacion,
    CriteriosDisponibilidad,
    SolicitudEquipos,
    Sugerencia,
)
from ..domain.asignaciones.ports import AsignacionRepository
from ..domain.identidad.entities import Usuario
from ..domain.inventario.entities import Equipo
from ..domain.inventario.ports import EquipoRepository
from ..domain.mantenimiento.ports import MantenimientoRepository
from ..domain.shared.enums import EstadoAsignacion
from ..domain.shared.errors import NoEncontradoError, ReglaNegocioError, ValidacionError
from ..domain.shared.ports import AuditoriaRepository, Reloj, UnitOfWork


class AsignacionService:
    def __init__(
        self,
        equipos: EquipoRepository,
        asignaciones: AsignacionRepository,
        mantenimientos: MantenimientoRepository,
        auditoria: AuditoriaRepository,
        uow: UnitOfWork,
        reloj: Reloj,
        max_horas_asignacion: float,
    ):
        self._equipos = equipos
        self._asignaciones = asignaciones
        self._mantenimientos = mantenimientos
        self._auditoria = auditoria
        self._uow = uow
        self._reloj = reloj
        self._max_horas = max_horas_asignacion

    # ---- disponibilidad
    def disponibles(self, criterios: CriteriosDisponibilidad) -> list[Equipo]:
        if criterios.fin <= criterios.inicio:
            raise ValidacionError("'fin' debe ser posterior a 'inicio'")
        return self._asignaciones.equipos_disponibles(criterios)

    # ---- asignación de un equipo concreto
    def asignar(self, actor: Usuario, equipo_id: int, actividad: str, inicio: datetime, fin: datetime) -> Asignacion:
        policies.validar_periodo(inicio, fin, self._max_horas)
        equipo = self._equipos.obtener(equipo_id)
        if equipo is None:
            raise NoEncontradoError("Equipo no encontrado")
        policies.verificar_asignable(
            equipo,
            self._asignaciones.ids_en_conflicto(equipo.id, inicio, fin),
            self._mantenimientos.hay_cruce(equipo.id, inicio, fin),
        )
        asignacion = self._asignaciones.guardar(
            Asignacion(equipo_id=equipo.id, usuario_id=actor.id, actividad=actividad, inicio=inicio, fin=fin)
        )
        self._auditoria.registrar(actor.id, "crear", "asignacion", asignacion.id, f"equipo={equipo.codigo}")
        self._uow.commit()
        return asignacion

    # ---- solicitud de varios equipos
    def sugerir(self, solicitud: SolicitudEquipos) -> Sugerencia:
        policies.validar_periodo(solicitud.inicio, solicitud.fin, self._max_horas)
        candidatos = self._candidatos(solicitud)
        return Sugerencia(
            solicitados=solicitud.cantidad,
            disponibles_compatibles=len(candidatos),
            equipos=candidatos[: solicitud.cantidad],
        )

    def solicitar(self, actor: Usuario, solicitud: SolicitudEquipos) -> list[Asignacion]:
        """Todo o nada: si no alcanzan los equipos compatibles, no se asigna ninguno."""
        sugerencia = self.sugerir(solicitud)
        if not sugerencia.suficientes:
            raise ReglaNegocioError(
                "No hay suficientes equipos compatibles disponibles para el periodo solicitado",
                info={
                    "solicitados": solicitud.cantidad,
                    "disponibles_compatibles": sugerencia.disponibles_compatibles,
                },
            )
        grupo = str(uuid.uuid4())
        asignaciones = self._asignaciones.guardar_varias(
            [
                Asignacion(
                    equipo_id=e.id,
                    usuario_id=actor.id,
                    actividad=solicitud.actividad,
                    inicio=solicitud.inicio,
                    fin=solicitud.fin,
                    grupo=grupo,
                )
                for e in sugerencia.equipos
            ]
        )
        self._auditoria.registrar(
            actor.id, "crear_solicitud", "asignacion", None, f"grupo={grupo}; equipos={len(asignaciones)}"
        )
        self._uow.commit()
        return asignaciones

    def _candidatos(self, solicitud: SolicitudEquipos) -> list[Equipo]:
        """Primero la zona pedida; otras zonas solo si se autoriza y no alcanzan."""
        if solicitud.zona_id is None:
            return self._asignaciones.equipos_disponibles(solicitud.criterios(None))
        candidatos = self._asignaciones.equipos_disponibles(solicitud.criterios(solicitud.zona_id))
        if len(candidatos) < solicitud.cantidad and solicitud.permitir_otras_zonas:
            ya = {e.id for e in candidatos}
            candidatos += [
                e for e in self._asignaciones.equipos_disponibles(solicitud.criterios(None)) if e.id not in ya
            ]
        return candidatos

    # ---- consulta y cancelación
    def listar(
        self,
        equipo_id: int | None,
        estado: EstadoAsignacion | None,
        desde: datetime | None,
        hasta: datetime | None,
        skip: int,
        limit: int,
    ) -> list[Asignacion]:
        return self._asignaciones.listar(equipo_id, estado, desde, hasta, skip, limit)

    def obtener(self, asignacion_id: int) -> Asignacion:
        asignacion = self._asignaciones.obtener(asignacion_id)
        if asignacion is None:
            raise NoEncontradoError("Asignación no encontrada")
        return asignacion

    def cancelar(self, actor: Usuario, asignacion_id: int) -> Asignacion:
        asignacion = self.obtener(asignacion_id)
        ahora = self._reloj()
        if asignacion.estado == EstadoAsignacion.cancelada:
            raise ReglaNegocioError("La asignación ya estaba cancelada")
        if asignacion.fin <= ahora:
            raise ReglaNegocioError("No se puede cancelar una asignación que ya terminó")
        asignacion.estado = EstadoAsignacion.cancelada
        asignacion.cancelada_en = ahora
        self._asignaciones.guardar(asignacion)
        self._auditoria.registrar(actor.id, "cancelar", "asignacion", asignacion.id)
        self._uow.commit()
        return asignacion
