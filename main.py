"""Punto de entrada de la API.

Ejecutar en desarrollo:
    uvicorn main:app --reload
Documentación interactiva (OpenAPI 3):  http://127.0.0.1:8000/docs
Panel con estadísticas y circuit breaker: http://127.0.0.1:8000/ui
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.errors import registrar_manejadores
from app.api.routers import analisis, asignaciones, auth, equipos, incidentes, usuarios
from app.config import APP_NAME, APP_VERSION
from app.infrastructure.persistence.bootstrap import init_db

PANEL_HTML = Path(__file__).parent / "app" / "api" / "static" / "dashboard.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API REST con arquitectura hexagonal (domain / application / infrastructure / api) para "
        "centralizar el inventario de computadores de las salas tecnológicas, gestionar disponibilidad y "
        "asignaciones sin conflictos de horario, dar seguimiento a incidentes y mantenimientos, y generar "
        "indicadores a partir de datos propios y de APIs públicas colombianas."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Estado", "description": "Verificación del servicio"},
        {"name": "Autenticación", "description": "Inicio de sesión con JWT"},
        {"name": "Usuarios y roles", "description": "Administración de usuarios y auditoría"},
        {"name": "Inventario", "description": "Zonas y equipos"},
        {"name": "Asignaciones", "description": "Disponibilidad y asignaciones con validación de conflictos"},
        {"name": "Incidentes y mantenimiento", "description": "Seguimiento técnico de los equipos"},
        {"name": "Análisis y optimización", "description": "Indicadores y recomendaciones por reglas"},
        {"name": "Analítica con DuckDB", "description": "Estadísticas descriptivas con SQL"},
        {"name": "APIs públicas colombianas", "description": "datos.gov.co y DANE con circuit breaker y retry"},
    ],
)
registrar_manejadores(app)


@app.get("/", tags=["Estado"])
def inicio():
    return {
        "mensaje": "Mi API funciona",
        "sistema": APP_NAME,
        "version": APP_VERSION,
        "documentacion": "/docs",
        "panel": "/ui",
    }


@app.get("/salud", tags=["Estado"])
def salud():
    return {"estado": "ok"}


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
def panel():
    """Panel web: inicia sesión con JWT y consulta la API desde el navegador."""
    return PANEL_HTML.read_text(encoding="utf-8")


for enrutador in (
    auth.router,
    usuarios.router,
    usuarios.router_auditoria,
    equipos.router_zonas,
    equipos.router,
    asignaciones.router,
    incidentes.router,
    incidentes.router_mantenimientos,
    analisis.router,
    analisis.router_analitica,
    analisis.router_datos_abiertos,
):
    app.include_router(enrutador)
