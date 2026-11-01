"""Reglas puras de incidentes y estado operativo del equipo."""
from ..shared.enums import EstadoEquipo, EstadoIncidente, Severidad
from ..shared.errors import ReglaNegocioError

SEVERIDADES_BLOQUEANTES = (Severidad.alta, Severidad.critica)

TRANSICIONES: dict[EstadoIncidente, set[EstadoIncidente]] = {
    EstadoIncidente.abierto: {EstadoIncidente.en_atencion, EstadoIncidente.resuelto},
    EstadoIncidente.en_atencion: {EstadoIncidente.resuelto},
    EstadoIncidente.resuelto: set(),
}


def derivar_estado(mantenimientos_abiertos: int, incidentes_graves_abiertos: int) -> EstadoEquipo:
    """El estado operativo se deriva de los registros, no se edita a mano.

    - Mantenimiento abierto               -> en_mantenimiento
    - Incidente grave/crítico sin cerrar  -> fuera_de_servicio
    - En otro caso                        -> disponible
    """
    if mantenimientos_abiertos:
        return EstadoEquipo.en_mantenimiento
    if incidentes_graves_abiertos:
        return EstadoEquipo.fuera_de_servicio
    return EstadoEquipo.disponible


def validar_transicion(actual: EstadoIncidente, nuevo: EstadoIncidente) -> None:
    if nuevo not in TRANSICIONES[actual]:
        raise ReglaNegocioError(f"Transición no permitida: {actual.value} → {nuevo.value}")
