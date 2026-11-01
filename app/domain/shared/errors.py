"""Errores del dominio. No conocen HTTP: la capa `api` decide cómo traducirlos."""


class DominioError(Exception):
    def __init__(self, mensaje: str, info: dict | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.info = info


class ReglaNegocioError(DominioError):
    """Se viola una regla de negocio (la API responde 409)."""


class NoEncontradoError(DominioError):
    """La entidad no existe (404)."""


class ValidacionError(DominioError, ValueError):
    """Dato inválido según el dominio (422). Hereda de ValueError para que Pydantic lo reconozca."""


class CredencialesInvalidasError(DominioError):
    """Usuario o contraseña incorrectos, o usuario inactivo (401)."""


class TokenInvalidoError(DominioError):
    """Token ausente, inválido o expirado (401)."""


class FuenteNoDisponibleError(DominioError):
    """Una API externa no responde y no hay datos en caché (503)."""
