"""Datos de demostración al arrancar y permisos del rol estudiante."""
from datetime import timedelta

from sqlalchemy import func, select

from app.config import ahora
from app.infrastructure.persistence import bootstrap
from app.infrastructure.persistence.database import Base, SessionLocal, engine
from app.infrastructure.persistence.demo_data import cargar_equipos
from app.infrastructure.persistence.orm import EquipoORM


def _periodo(hora=8, horas=2):
    base = (ahora() + timedelta(days=1)).replace(hour=hora, minute=0, second=0, microsecond=0)
    return base.isoformat(), (base + timedelta(hours=horas)).isoformat()


def _login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _total_equipos() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(EquipoORM))


# ------------------------------------------------------------------ datos de demostración
def test_arranque_con_base_vacia_carga_20_equipos_y_usuarios(client, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(bootstrap, "CARGAR_DATOS_DEMO", True)
    bootstrap.init_db()

    encargado = _login(client, "encargado1@umb.local", "Encargado123!")
    _login(client, "encargado2@umb.local", "Encargado123!")
    _login(client, "estudiante@umb.local", "Estudiante123!")
    equipos = client.get("/equipos", headers=encargado, params={"limit": 100}).json()
    assert len(equipos) == 20
    assert sum(e["tipo"] == "all_in_one" for e in equipos) == 15
    assert sum(e["tipo"] == "portatil" for e in equipos) == 5


def test_reiniciar_no_duplica_equipos_ni_usuarios(client, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(bootstrap, "CARGAR_DATOS_DEMO", True)
    bootstrap.init_db()
    bootstrap.init_db()
    bootstrap.init_db()
    assert _total_equipos() == 20
    admin = _login(client, "admin@umb.local", "Admin12345!")
    assert len(client.get("/usuarios", headers=admin).json()) == 4  # admin + 2 encargados + estudiante


def test_no_pisa_un_inventario_existente(client, admin, crear_equipo, monkeypatch):
    crear_equipo(codigo="LAB-001")  # inventario real previo
    monkeypatch.setattr(bootstrap, "CARGAR_DATOS_DEMO", True)
    bootstrap.init_db()
    assert _total_equipos() == 1


def test_demo_desactivable_con_la_variable(client, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(bootstrap, "CARGAR_DATOS_DEMO", False)
    bootstrap.init_db()
    assert _total_equipos() == 0
    r = client.post("/auth/login", json={"email": "estudiante@umb.local", "password": "Estudiante123!"})
    assert r.status_code == 401


def test_script_agrega_solo_los_equipos_que_faltan(client, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(bootstrap, "CARGAR_DATOS_DEMO", True)
    bootstrap.init_db()  # 15 AIO + 5 PRT
    with SessionLocal() as db:
        assert cargar_equipos(db, 15, 5) == 0  # nada nuevo
        assert cargar_equipos(db, 20, 7) == 7  # 5 AIO + 2 PRT adicionales
        db.commit()
    assert _total_equipos() == 27


# ------------------------------------------------------------------ rol estudiante
def test_estudiante_consulta_equipos_y_disponibilidad(client, usuarios, crear_equipo):
    crear_equipo()
    est = usuarios["estudiante"]
    assert client.get("/equipos", headers=est).status_code == 200
    assert client.get("/zonas", headers=est).status_code == 200
    inicio, fin = _periodo()
    r = client.get("/equipos/disponibles", headers=est, params={"inicio": inicio, "fin": fin})
    assert r.status_code == 200 and len(r.json()) == 1


def test_estudiante_no_presta_ni_ve_prestamos_ajenos(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    inicio, fin = _periodo()
    cuerpo = {"equipo_id": equipo["id"], "actividad": "Préstamo", "inicio": inicio, "fin": fin}
    est = usuarios["estudiante"]
    assert client.post("/asignaciones", headers=est, json=cuerpo).status_code == 403

    creada = client.post("/asignaciones", headers=usuarios["encargado_sala"], json=cuerpo)
    assert creada.status_code == 201
    asignacion_id = creada.json()["id"]
    assert client.get("/asignaciones", headers=est).status_code == 403
    assert client.get(f"/asignaciones/{asignacion_id}", headers=est).status_code == 403
    assert client.patch(f"/asignaciones/{asignacion_id}/cancelar", headers=est).status_code == 403


def test_estudiante_sin_acceso_a_gestion_ni_analisis(client, usuarios):
    est = usuarios["estudiante"]
    assert client.get("/usuarios", headers=est).status_code == 403
    assert client.get("/auditoria", headers=est).status_code == 403
    assert client.get("/analisis/resumen", headers=est).status_code == 403
    assert client.get("/incidentes", headers=est).status_code == 403
    assert client.get("/mantenimientos", headers=est).status_code == 403
