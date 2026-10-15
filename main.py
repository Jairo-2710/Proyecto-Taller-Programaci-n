"""Punto de entrada de la API.

Ejecutar en desarrollo:
    uvicorn main:app --reload
Documentación interactiva (OpenAPI 3):  http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import APP_NAME, APP_VERSION
from app.errors import ReglaNegocioError
from app.init_db import init_db
from app.routers import analisis, asignaciones, auditoria, auth, equipos, incidentes, mantenimientos, usuarios, zonas


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API REST para centralizar el inventario de computadores de las salas tecnológicas, "
        "gestionar disponibilidad y asignaciones sin conflictos de horario, dar seguimiento a "
        "incidentes y mantenimientos, y generar indicadores y recomendaciones a partir de los datos."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Estado", "description": "Verificación del servicio"},
        {"name": "Autenticación", "description": "Inicio de sesión con JWT"},
        {"name": "Usuarios y roles", "description": "Administración de usuarios y auditoría"},
        {"name": "Inventario", "description": "Zonas y equipos"},
        {"name": "Asignaciones", "description": "Disponibilidad y asignaciones con validación de conflictos"},
        {"name": "Incidentes y mantenimiento", "description": "Seguimiento técnico de los equipos"},
        {"name": "Análisis y optimización", "description": "Indicadores y recomendaciones"},
    ],
)


@app.exception_handler(ReglaNegocioError)
async def manejar_regla_negocio(_: Request, error: ReglaNegocioError):
    contenido = {"detail": error.mensaje}
    if error.info:
        contenido["info"] = error.info
    return JSONResponse(status_code=error.status_code, content=contenido)


@app.get("/", tags=["Estado"])
def inicio():
    return {"mensaje": "Mi API funciona", "sistema": APP_NAME, "version": APP_VERSION, "documentacion": "/docs"}


@app.get("/salud", tags=["Estado"])
def salud():
    return {"estado": "ok"}


for modulo in (auth, usuarios, zonas, equipos, asignaciones, incidentes, mantenimientos, analisis, auditoria):
    app.include_router(modulo.router)
