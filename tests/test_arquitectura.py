"""Inyección de dependencias (puertos con mocks), endpoints nuevos con dependency_overrides y reglas de capas."""
import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.identidad import AuthService, UsuarioService
from app.api.container import get_datos_abiertos_service
from app.domain.analitica.entities import EstadoFuente
from app.domain.identidad.entities import Usuario
from app.domain.shared.enums import EstadoCircuito, Rol
from app.domain.shared.errors import CredencialesInvalidasError, ReglaNegocioError
from main import app

RAIZ = Path(__file__).resolve().parent.parent / "app"


def test_auth_service_con_puertos_falsos():
    usuarios, hasher, tokens = MagicMock(), MagicMock(), MagicMock()
    usuarios.por_email.return_value = Usuario("A", "a@x.co", "h", Rol.administrador, id=7)
    hasher.verificar.return_value = True
    tokens.crear.return_value = "jwt"
    assert AuthService(usuarios, hasher, tokens).login("A@X.co", "pw") == ("jwt", Rol.administrador)
    tokens.crear.assert_called_once_with(7, "administrador")


def test_auth_service_rechaza_clave_incorrecta():
    usuarios, hasher, tokens = MagicMock(), MagicMock(), MagicMock()
    usuarios.por_email.return_value = Usuario("A", "a@x.co", "h", Rol.administrador, id=7)
    hasher.verificar.return_value = False
    with pytest.raises(CredencialesInvalidasError):
        AuthService(usuarios, hasher, tokens).login("a@x.co", "mal")
    tokens.crear.assert_not_called()


def test_usuario_service_no_duplica_correo_y_no_hace_commit():
    usuarios, hasher, auditoria, uow = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    usuarios.por_email.return_value = object()
    with pytest.raises(ReglaNegocioError):
        UsuarioService(usuarios, hasher, auditoria, uow).crear(MagicMock(), "N", "a@x.co", "pw", Rol.docente)
    uow.commit.assert_not_called()
    usuarios.guardar.assert_not_called()


def test_usuario_service_crea_audita_y_confirma():
    usuarios, hasher, auditoria, uow = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    usuarios.por_email.return_value = None
    hasher.hashear.return_value = "hash"
    usuarios.guardar.side_effect = lambda u: u
    UsuarioService(usuarios, hasher, auditoria, uow).crear(MagicMock(id=1), "N", "A@X.co", "pw", Rol.docente)
    auditoria.registrar.assert_called_once()
    uow.commit.assert_called_once()


def test_endpoint_estado_con_servicio_falso(client, admin):
    falso = MagicMock()
    falso.estados.return_value = [
        EstadoFuente("datos.gov.co", "d", "https://x/resource/a.json", EstadoCircuito.abierto, 3, ["CLOSED → OPEN: 3 fallos consecutivos"])
    ]
    app.dependency_overrides[get_datos_abiertos_service] = lambda: falso
    try:
        r = client.get("/datos-abiertos/estado", headers=admin)
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()[0]["estado_circuito_en"] == "OPEN"


def test_endpoints_analiticos_con_duckdb(client, admin, crear_equipo):
    crear_equipo()
    crear_equipo(tipo="portatil", zona_id=2, ram_gb=8)
    r = client.get("/analitica/equipos", headers=admin)
    assert r.status_code == 200
    assert sum(f["equipos"] for f in r.json()["por_zona_tipo"]) == 2
    assert client.get("/analitica/asignaciones", headers=admin).status_code == 200


def test_endpoints_analiticos_requieren_autenticacion(client):
    assert client.get("/analitica/equipos").status_code == 401
    assert client.get("/datos-abiertos/estado").status_code == 401


def test_panel_ui_publico(client):
    r = client.get("/ui")
    assert r.status_code == 200 and "Panel" in r.text


def test_dominio_y_aplicacion_no_dependen_de_infraestructura():
    """Regla hexagonal: las capas internas no importan frameworks ni capas externas."""
    prohibidos = ("fastapi", "sqlalchemy", "duckdb", "jwt", "httpx", "pydantic")
    for capa in ("domain", "application"):
        for archivo in (RAIZ / capa).rglob("*.py"):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
                modulos = []
                if isinstance(nodo, ast.Import):
                    modulos = [a.name for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom):
                    modulos = [("." * nodo.level) + (nodo.module or "")]
                for m in modulos:
                    assert m.split(".")[0] not in prohibidos, f"{archivo}: importa {m}"
                    assert "infrastructure" not in m and ".api" not in m, f"{archivo}: importa {m}"
