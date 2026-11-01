"""Traduce los errores del dominio a respuestas HTTP (el dominio no sabe de HTTP)."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..domain.shared.errors import (
    CredencialesInvalidasError,
    DominioError,
    FuenteNoDisponibleError,
    NoEncontradoError,
    ReglaNegocioError,
    TokenInvalidoError,
    ValidacionError,
)

_ESTADOS: list[tuple[type[DominioError], int]] = [
    (ReglaNegocioError, 409),
    (NoEncontradoError, 404),
    (ValidacionError, 422),
    (CredencialesInvalidasError, 401),
    (TokenInvalidoError, 401),
    (FuenteNoDisponibleError, 503),
]


def registrar_manejadores(app: FastAPI) -> None:
    for tipo, estado in _ESTADOS:

        def manejador(_: Request, error: DominioError, estado: int = estado):
            contenido: dict = {"detail": error.mensaje}
            if error.info:
                contenido["info"] = error.info
            encabezados = {"WWW-Authenticate": "Bearer"} if estado == 401 else None
            return JSONResponse(status_code=estado, content=contenido, headers=encabezados)

        app.add_exception_handler(tipo, manejador)
