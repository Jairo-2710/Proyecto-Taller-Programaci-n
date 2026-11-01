import os

# Debe definirse antes de importar la aplicación: base de datos en memoria para las pruebas.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_EMAIL"] = "admin@umb.local"
os.environ["ADMIN_PASSWORD"] = "Admin12345!"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.infrastructure.persistence.database import Base, engine  # noqa: E402
from app.infrastructure.persistence.bootstrap import init_db  # noqa: E402
from main import app  # noqa: E402

CLAVE = "Clave12345!"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    init_db()
    return TestClient(app)


def _login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return _login(client, "admin@umb.local", "Admin12345!")


@pytest.fixture()
def usuarios(client, admin):
    """Un usuario por rol, devuelve {rol: encabezados}."""
    tokens = {"administrador": admin}
    for rol in ("encargado_sala", "soporte", "docente", "coordinador"):
        r = client.post(
            "/usuarios",
            headers=admin,
            json={"nombre": f"Usuario {rol}", "email": f"{rol}@umb.local", "password": CLAVE, "rol": rol},
        )
        assert r.status_code == 201, r.text
        tokens[rol] = _login(client, f"{rol}@umb.local", CLAVE)
    return tokens


@pytest.fixture()
def crear_equipo(client, admin):
    contador = {"n": 0}

    def _crear(zona_id=1, tipo="all_in_one", ram_gb=16, software=None, codigo=None):
        contador["n"] += 1
        r = client.post(
            "/equipos",
            headers=admin,
            json={
                "codigo": codigo or f"EQ-{contador['n']:03d}",
                "tipo": tipo,
                "zona_id": zona_id,
                "ram_gb": ram_gb,
                "almacenamiento_gb": 512,
                "software": software or [],
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _crear
