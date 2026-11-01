from enum import StrEnum


class Rol(StrEnum):
    administrador = "administrador"
    encargado_sala = "encargado_sala"
    soporte = "soporte"
    docente = "docente"
    coordinador = "coordinador"


class TipoEquipo(StrEnum):
    all_in_one = "all_in_one"
    portatil = "portatil"


class EstadoEquipo(StrEnum):
    disponible = "disponible"
    en_mantenimiento = "en_mantenimiento"
    fuera_de_servicio = "fuera_de_servicio"


class EstadoAsignacion(StrEnum):
    activa = "activa"
    cancelada = "cancelada"


class Severidad(StrEnum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


class EstadoIncidente(StrEnum):
    abierto = "abierto"
    en_atencion = "en_atencion"
    resuelto = "resuelto"


class TipoMantenimiento(StrEnum):
    preventivo = "preventivo"
    correctivo = "correctivo"


class EstadoCircuito(StrEnum):
    """Estados del circuit breaker."""

    cerrado = "cerrado"  # CLOSED: las llamadas pasan con normalidad
    abierto = "abierto"  # OPEN: se rechazan las llamadas sin intentarlas
    semiabierto = "semiabierto"  # HALF_OPEN: se permite una llamada de prueba

    @property
    def ingles(self) -> str:
        return {"cerrado": "CLOSED", "abierto": "OPEN", "semiabierto": "HALF_OPEN"}[self.value]
