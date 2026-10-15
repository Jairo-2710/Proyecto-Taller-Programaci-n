"""Pruebas de reglas de negocio, validación, permisos y escenarios principales."""
from datetime import datetime, timedelta

from app.config import ahora


def _manana(hora_inicio=8, horas=2, dias=1):
    base = (ahora() + timedelta(days=dias)).replace(hour=hora_inicio, minute=0, second=0, microsecond=0)
    return base.isoformat(), (base + timedelta(hours=horas)).isoformat()


# ------------------------------------------------------------------ Autenticación y permisos
def test_login_correcto_e_incorrecto(client):
    ok = client.post("/auth/login", json={"email": "admin@umb.local", "password": "Admin12345!"})
    assert ok.status_code == 200 and ok.json()["rol"] == "administrador"
    mal = client.post("/auth/login", json={"email": "admin@umb.local", "password": "otra"})
    assert mal.status_code == 401


def test_sin_token_es_401(client):
    assert client.get("/equipos").status_code == 401
    assert client.get("/equipos", headers={"Authorization": "Bearer falso"}).status_code == 401


def test_solo_admin_modifica_inventario(client, usuarios):
    cuerpo = {"codigo": "AIO-001", "tipo": "all_in_one", "zona_id": 1, "ram_gb": 16, "almacenamiento_gb": 512}
    for rol in ("encargado_sala", "soporte", "docente", "coordinador"):
        assert client.post("/equipos", headers=usuarios[rol], json=cuerpo).status_code == 403
    assert client.post("/equipos", headers=usuarios["administrador"], json=cuerpo).status_code == 201


def test_docente_consulta_disponibilidad_pero_no_asigna(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    inicio, fin = _manana()
    r = client.get("/equipos/disponibles", headers=usuarios["docente"], params={"inicio": inicio, "fin": fin})
    assert r.status_code == 200 and len(r.json()) == 1
    r = client.post(
        "/asignaciones",
        headers=usuarios["docente"],
        json={"equipo_id": equipo["id"], "actividad": "Clase", "inicio": inicio, "fin": fin},
    )
    assert r.status_code == 403


def test_usuarios_solo_admin_y_correo_unico(client, usuarios, admin):
    assert client.get("/usuarios", headers=usuarios["soporte"]).status_code == 403
    r = client.post(
        "/usuarios",
        headers=admin,
        json={"nombre": "Duplicado", "email": "SOPORTE@umb.local", "password": "Clave12345!", "rol": "soporte"},
    )
    assert r.status_code == 409


# ------------------------------------------------------------------ Inventario y validación
def test_codigo_unico_y_validaciones(client, admin, crear_equipo):
    crear_equipo(codigo="AIO-001")
    duplicado = {"codigo": "aio-001", "tipo": "all_in_one", "zona_id": 1, "ram_gb": 8, "almacenamiento_gb": 256}
    assert client.post("/equipos", headers=admin, json=duplicado).status_code == 409
    invalido = {**duplicado, "codigo": "X", "ram_gb": 0}
    assert client.post("/equipos", headers=admin, json=invalido).status_code == 422
    sin_zona = {**duplicado, "codigo": "AIO-999", "zona_id": 999}
    assert client.post("/equipos", headers=admin, json=sin_zona).status_code == 404


def test_consultar_inventario_por_zona_tipo_y_estado(client, usuarios, crear_equipo):
    crear_equipo(zona_id=1, tipo="all_in_one")
    crear_equipo(zona_id=2, tipo="portatil")
    h = usuarios["docente"]
    assert len(client.get("/equipos", headers=h).json()) == 2
    assert len(client.get("/equipos", headers=h, params={"zona_id": 2}).json()) == 1
    assert client.get("/equipos", headers=h, params={"tipo": "portatil"}).json()[0]["zona_id"] == 2
    assert client.get("/equipos", headers=h, params={"estado": "fuera_de_servicio"}).json() == []


def test_desactivar_equipo_es_baja_logica(client, admin, crear_equipo):
    equipo = crear_equipo()
    r = client.delete(f"/equipos/{equipo['id']}", headers=admin)
    assert r.status_code == 200 and r.json()["activo"] is False
    assert client.get("/equipos", headers=admin).json() == []
    assert len(client.get("/equipos", headers=admin, params={"activo": False}).json()) == 1


# ------------------------------------------------------------------ Asignaciones y conflictos
def test_asignacion_duplicada_en_horario_cruzado_es_rechazada(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    gestor = usuarios["encargado_sala"]
    inicio, fin = _manana(8, 2)
    cuerpo = {"equipo_id": equipo["id"], "actividad": "Clase de programación", "inicio": inicio, "fin": fin}
    assert client.post("/asignaciones", headers=gestor, json=cuerpo).status_code == 201

    # Mismo periodo y periodo parcialmente cruzado -> conflicto
    assert client.post("/asignaciones", headers=gestor, json=cuerpo).status_code == 409
    i2, f2 = _manana(9, 2)
    cruzado = {**cuerpo, "inicio": i2, "fin": f2}
    r = client.post("/asignaciones", headers=gestor, json=cruzado)
    assert r.status_code == 409 and "asignaciones_en_conflicto" in r.json()["info"]

    # Periodo contiguo (empieza justo cuando termina la otra) -> permitido
    i3, f3 = _manana(10, 2)
    contiguo = {**cuerpo, "inicio": i3, "fin": f3}
    assert client.post("/asignaciones", headers=gestor, json=contiguo).status_code == 201


def test_equipo_asignado_no_aparece_disponible_y_cancelar_lo_libera(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    gestor = usuarios["encargado_sala"]
    inicio, fin = _manana()
    a = client.post(
        "/asignaciones",
        headers=gestor,
        json={"equipo_id": equipo["id"], "actividad": "Taller", "inicio": inicio, "fin": fin},
    ).json()
    params = {"inicio": inicio, "fin": fin}
    assert client.get("/equipos/disponibles", headers=gestor, params=params).json() == []
    assert client.patch(f"/asignaciones/{a['id']}/cancelar", headers=gestor).json()["estado"] == "cancelada"
    assert len(client.get("/equipos/disponibles", headers=gestor, params=params).json()) == 1
    assert client.patch(f"/asignaciones/{a['id']}/cancelar", headers=gestor).status_code == 409


def test_validacion_de_periodo(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    inicio, _ = _manana()
    r = client.post(
        "/asignaciones",
        headers=usuarios["encargado_sala"],
        json={"equipo_id": equipo["id"], "actividad": "Clase", "inicio": inicio, "fin": inicio},
    )
    assert r.status_code == 422
    largo = (datetime.fromisoformat(inicio) + timedelta(hours=20)).isoformat()
    r = client.post(
        "/asignaciones",
        headers=usuarios["encargado_sala"],
        json={"equipo_id": equipo["id"], "actividad": "Clase", "inicio": inicio, "fin": largo},
    )
    assert r.status_code == 422


def test_compatibilidad_de_requisitos(client, usuarios, crear_equipo):
    crear_equipo(ram_gb=8, software=["Python"])
    bueno = crear_equipo(ram_gb=16, software=["Python", "PostgreSQL"])
    inicio, fin = _manana()
    r = client.get(
        "/equipos/disponibles",
        headers=usuarios["docente"],
        params={"inicio": inicio, "fin": fin, "ram_min": 16, "software": ["postgresql"]},
    )
    assert [e["id"] for e in r.json()] == [bueno["id"]]


def test_solicitud_multiple_todo_o_nada_y_otras_zonas(client, usuarios, crear_equipo):
    for _ in range(3):
        crear_equipo(zona_id=1)
    for _ in range(2):
        crear_equipo(zona_id=2, tipo="portatil")
    gestor = usuarios["encargado_sala"]
    inicio, fin = _manana()
    base = {"actividad": "Parcial", "inicio": inicio, "fin": fin, "cantidad": 4, "zona_id": 1}

    # Zona 1 solo tiene 3: sin permiso para otras zonas no se asigna nada.
    r = client.post("/asignaciones/solicitud", headers=gestor, json=base)
    assert r.status_code == 409 and r.json()["info"] == {"solicitados": 4, "disponibles_compatibles": 3}
    assert client.get("/asignaciones", headers=gestor).json() == []

    # La sugerencia no crea nada.
    s = client.post("/asignaciones/sugerencia", headers=gestor, json={**base, "permitir_otras_zonas": True}).json()
    assert s["suficientes"] is True and len(s["equipos_sugeridos"]) == 4
    assert client.get("/asignaciones", headers=gestor).json() == []

    # Con otras zonas permitidas se completa, primero los de la zona pedida.
    r = client.post("/asignaciones/solicitud", headers=gestor, json={**base, "permitir_otras_zonas": True})
    assert r.status_code == 201 and len(r.json()) == 4
    assert len({a["grupo"] for a in r.json()}) == 1
    zonas = [client.get(f"/equipos/{a['equipo_id']}", headers=gestor).json()["zona_id"] for a in r.json()]
    assert zonas.count(1) == 3 and zonas.count(2) == 1


# ------------------------------------------------------------------ Incidentes y mantenimiento
def test_incidente_critico_deja_equipo_fuera_de_servicio_y_no_asignable(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    inicio, fin = _manana()
    r = client.post(
        "/incidentes",
        headers=usuarios["docente"],
        json={"equipo_id": equipo["id"], "descripcion": "No enciende la pantalla", "severidad": "critica"},
    )
    assert r.status_code == 201
    incidente = r.json()
    assert client.get(f"/equipos/{equipo['id']}", headers=usuarios["docente"]).json()["estado"] == "fuera_de_servicio"
    assert client.get("/equipos/disponibles", headers=usuarios["docente"], params={"inicio": inicio, "fin": fin}).json() == []
    r = client.post(
        "/asignaciones",
        headers=usuarios["encargado_sala"],
        json={"equipo_id": equipo["id"], "actividad": "Clase", "inicio": inicio, "fin": fin},
    )
    assert r.status_code == 409 and "fuera de servicio" in r.json()["detail"]

    # Flujo de atención: no se puede resolver sin acciones ni saltarse el orden inverso.
    soporte = usuarios["soporte"]
    url = f"/incidentes/{incidente['id']}"
    assert client.patch(url, headers=soporte, json={"estado": "resuelto"}).status_code == 409
    assert client.patch(url, headers=soporte, json={"estado": "en_atencion"}).status_code == 200
    r = client.patch(url, headers=soporte, json={"estado": "resuelto", "acciones": "Cambio de fuente de poder"})
    assert r.status_code == 200 and r.json()["fecha_cierre"] is not None
    assert client.get(f"/equipos/{equipo['id']}", headers=soporte).json()["estado"] == "disponible"
    assert client.patch(url, headers=soporte, json={"estado": "en_atencion"}).status_code == 409


def test_incidente_leve_no_bloquea_el_equipo(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    client.post(
        "/incidentes",
        headers=usuarios["docente"],
        json={"equipo_id": equipo["id"], "descripcion": "Teclado con una tecla suelta", "severidad": "baja"},
    )
    assert client.get(f"/equipos/{equipo['id']}", headers=usuarios["docente"]).json()["estado"] == "disponible"


def test_mantenimiento_bloquea_y_cierre_libera(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    soporte, gestor = usuarios["soporte"], usuarios["encargado_sala"]
    inicio, fin = _manana()
    asignacion = client.post(
        "/asignaciones",
        headers=gestor,
        json={"equipo_id": equipo["id"], "actividad": "Clase", "inicio": inicio, "fin": fin},
    ).json()

    r = client.post(
        "/mantenimientos",
        headers=soporte,
        json={"equipo_id": equipo["id"], "tipo": "preventivo", "descripcion": "Limpieza y actualización"},
    )
    assert r.status_code == 201
    mant = r.json()
    assert mant["asignaciones_afectadas"] == [asignacion["id"]]  # avisa, no cancela por su cuenta
    assert client.get(f"/equipos/{equipo['id']}", headers=soporte).json()["estado"] == "en_mantenimiento"
    # No se permite abrir un segundo mantenimiento ni asignar mientras esté abierto.
    assert client.post(
        "/mantenimientos",
        headers=soporte,
        json={"equipo_id": equipo["id"], "tipo": "correctivo", "descripcion": "Otro mantenimiento"},
    ).status_code == 409
    otro = _manana(14, 2)
    assert client.post(
        "/asignaciones",
        headers=gestor,
        json={"equipo_id": equipo["id"], "actividad": "Otra", "inicio": otro[0], "fin": otro[1]},
    ).status_code == 409

    cierre = client.patch(f"/mantenimientos/{mant['id']}/cerrar", headers=soporte, json={"acciones": "Limpieza completa"})
    assert cierre.status_code == 200 and cierre.json()["fin"] is not None
    assert client.get(f"/equipos/{equipo['id']}", headers=soporte).json()["estado"] == "disponible"
    assert client.patch(f"/mantenimientos/{mant['id']}/cerrar", headers=soporte, json={"acciones": "Otra vez"}).status_code == 409


def test_solo_soporte_y_admin_gestionan_mantenimiento(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    r = client.post(
        "/mantenimientos",
        headers=usuarios["encargado_sala"],
        json={"equipo_id": equipo["id"], "tipo": "preventivo", "descripcion": "Intento no autorizado"},
    )
    assert r.status_code == 403


def test_historial_del_equipo_y_auditoria(client, usuarios, crear_equipo, admin):
    equipo = crear_equipo()
    inicio, fin = _manana()
    client.post(
        "/asignaciones",
        headers=usuarios["encargado_sala"],
        json={"equipo_id": equipo["id"], "actividad": "Clase", "inicio": inicio, "fin": fin},
    )
    client.post(
        "/incidentes",
        headers=usuarios["docente"],
        json={"equipo_id": equipo["id"], "descripcion": "Se reinicia solo", "severidad": "media"},
    )
    h = client.get(f"/equipos/{equipo['id']}/historial", headers=usuarios["soporte"]).json()
    assert len(h["asignaciones"]) == 1 and len(h["incidentes"]) == 1 and h["mantenimientos"] == []
    assert client.get(f"/equipos/{equipo['id']}/historial", headers=usuarios["docente"]).status_code == 403
    entidades = {a["entidad"] for a in client.get("/auditoria", headers=admin).json()}
    assert {"usuario", "equipo", "asignacion", "incidente"} <= entidades
    assert client.get("/auditoria", headers=usuarios["soporte"]).status_code == 403


# ------------------------------------------------------------------ Análisis y optimización
def _asignar(client, headers, equipo_id, inicio, horas):
    r = client.post(
        "/asignaciones",
        headers=headers,
        json={
            "equipo_id": equipo_id,
            "actividad": "Práctica",
            "inicio": inicio.isoformat(),
            "fin": (inicio + timedelta(hours=horas)).isoformat(),
        },
    )
    assert r.status_code == 201, r.text


def test_indicador_de_utilizacion_se_calcula_correctamente(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    otro = crear_equipo()
    dia = datetime(2026, 9, 1)
    _asignar(client, usuarios["encargado_sala"], equipo["id"], dia.replace(hour=8), 7)  # 7 h de 14 h operativas
    params = {"desde": dia.isoformat(), "hasta": (dia + timedelta(days=1)).isoformat()}
    datos = {u["equipo_id"]: u for u in client.get("/analisis/utilizacion", headers=usuarios["coordinador"], params=params).json()}
    assert datos[equipo["id"]]["horas_asignadas"] == 7.0
    assert datos[equipo["id"]]["utilizacion"] == 0.5
    assert datos[equipo["id"]]["clasificacion"] == "normal"
    assert datos[otro["id"]]["utilizacion"] == 0.0 and datos[otro["id"]]["clasificacion"] == "baja"
    assert client.get("/analisis/utilizacion", headers=usuarios["docente"], params=params).status_code == 403


def test_recomendaciones_sin_datos_suficientes_no_inventan_patrones(client, usuarios, crear_equipo):
    crear_equipo()
    r = client.get("/analisis/recomendaciones", headers=usuarios["coordinador"]).json()
    assert r["datos_suficientes"] is False
    assert all(x["tipo"] not in ("redistribuir_demanda", "equipos_subutilizados") for x in r["recomendaciones"])
    d = client.get("/analisis/demanda", headers=usuarios["coordinador"]).json()
    assert d["datos_suficientes"] is False and d["mensaje"]


def test_recomienda_redistribuir_cuando_una_zona_esta_saturada(client, usuarios, crear_equipo):
    saturados = [crear_equipo(zona_id=1) for _ in range(2)]
    crear_equipo(zona_id=2, tipo="portatil")
    gestor = usuarios["encargado_sala"]
    desde = datetime(2026, 9, 1)
    # 7 días, 12 h diarias en los dos equipos de la zona 1 -> utilización 12/14 ≈ 86 %
    for dia in range(7):
        for e in saturados:
            _asignar(client, gestor, e["id"], desde + timedelta(days=dia, hours=7), 12)
    params = {"desde": desde.isoformat(), "hasta": (desde + timedelta(days=7)).isoformat()}
    r = client.get("/analisis/recomendaciones", headers=usuarios["coordinador"], params=params).json()
    assert r["datos_suficientes"] is True
    tipos = [x["tipo"] for x in r["recomendaciones"]]
    assert "redistribuir_demanda" in tipos and "equipos_subutilizados" in tipos
    assert r["recomendaciones"][0]["prioridad"] == "alta"

    demanda = client.get("/analisis/demanda", headers=usuarios["coordinador"], params=params).json()
    zona1 = next(z for z in demanda["zonas"] if z["zona_id"] == 1)
    assert zona1["horas_asignadas"] == 168.0 and zona1["utilizacion"] > 0.8
    assert zona1["por_hora"]["7"] == 14.0  # 2 equipos × 7 días en la franja de 7:00 a 8:00


def test_recomienda_revision_tecnica_por_incidentes_reiterados(client, usuarios, crear_equipo):
    equipo = crear_equipo()
    for i in range(3):
        client.post(
            "/incidentes",
            headers=usuarios["docente"],
            json={"equipo_id": equipo["id"], "descripcion": f"Falla número {i}", "severidad": "baja"},
        )
    r = client.get("/analisis/recomendaciones", headers=usuarios["coordinador"]).json()
    assert any(x["tipo"] == "revision_tecnica" and x["equipo_ids"] == [equipo["id"]] for x in r["recomendaciones"])
    inc = client.get("/analisis/incidentes", headers=usuarios["coordinador"]).json()
    assert inc[0]["incidentes"] == 3 and inc[0]["abiertos"] == 3


def test_resumen_general(client, usuarios, crear_equipo):
    crear_equipo(zona_id=1)
    crear_equipo(zona_id=2, tipo="portatil")
    r = client.get("/analisis/resumen", headers=usuarios["coordinador"]).json()
    assert r["equipos_activos"] == 2 and r["equipos_por_estado"]["disponible"] == 2
    assert r["equipos_por_zona"] == {"Sala All-in-One": 1, "Sala Portátiles": 1}


def test_salud_y_openapi(client):
    assert client.get("/salud").json() == {"estado": "ok"}
    esquema = client.get("/openapi.json").json()
    assert esquema["openapi"].startswith("3.")
    assert "/asignaciones/solicitud" in esquema["paths"]
