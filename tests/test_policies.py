from datetime import datetime, timedelta

import pytest

from app.domain.asignaciones.policies import (
    validar_periodo,
    periodos_se_cruzan,
    verificar_asignable,
)
from app.domain.mantenimiento.policies import (
    derivar_estado,
    validar_transicion,
)
from app.domain.inventario.entities import Equipo
from app.domain.shared.enums import (
    EstadoEquipo,
    EstadoIncidente,
    TipoEquipo,
)
from app.domain.shared.errors import (
    ReglaNegocioError,
    ValidacionError,
)


INICIO = datetime(2026, 11, 18, 8, 0, 0)


def crear_equipo(**cambios):
    datos = {
        "codigo": "EQ-001",
        "tipo": TipoEquipo.all_in_one,
        "zona_id": 1,
        "ram_gb": 16,
        "almacenamiento_gb": 512,
    }
    datos.update(cambios)
    return Equipo(**datos)


# VALIDACIÓN DE PERIODOS

def test_validar_periodo_correcto():
    validar_periodo(INICIO, INICIO + timedelta(hours=2), 3)


def test_validar_periodo_duracion_exacta_permitida():
    validar_periodo(INICIO, INICIO + timedelta(hours=2), 2)


@pytest.mark.parametrize(
    "fin",
    [
        INICIO,
        INICIO - timedelta(minutes=1),
    ],
)
def test_validar_periodo_rechaza_fecha_final_invalida(fin):
    with pytest.raises(ValidacionError) as exc:
        validar_periodo(INICIO, fin, 3)

    assert str(exc.value) == "'fin' debe ser posterior a 'inicio'"


def test_validar_periodo_rechaza_duracion_superior():
    fin = INICIO + timedelta(hours=2, seconds=1)

    with pytest.raises(ValidacionError) as exc:
        validar_periodo(INICIO, fin, 2)

    assert str(exc.value) == "Una asignación no puede superar 2 horas"


# CRUCE DE PERIODOS

def test_periodos_se_cruzan_parcialmente():
    resultado = periodos_se_cruzan(
        INICIO,
        INICIO + timedelta(hours=3),
        INICIO + timedelta(hours=2),
        INICIO + timedelta(hours=4),
    )

    assert resultado is True


def test_periodos_se_cruzan_si_uno_contiene_al_otro():
    resultado = periodos_se_cruzan(
        INICIO,
        INICIO + timedelta(hours=5),
        INICIO + timedelta(hours=1),
        INICIO + timedelta(hours=2),
    )

    assert resultado is True


def test_periodos_identicos_se_cruzan():
    fin = INICIO + timedelta(hours=2)

    assert periodos_se_cruzan(INICIO, fin, INICIO, fin) is True


@pytest.mark.parametrize(
    "ini_b, fin_b",
    [
        (
            INICIO + timedelta(hours=3),
            INICIO + timedelta(hours=5),
        ),
        (
            INICIO - timedelta(hours=2),
            INICIO,
        ),
    ],
)
def test_periodos_contiguos_no_se_cruzan(ini_b, fin_b):
    assert periodos_se_cruzan(
        INICIO,
        INICIO + timedelta(hours=3),
        ini_b,
        fin_b,
    ) is False


def test_periodos_separados_no_se_cruzan():
    assert periodos_se_cruzan(
        INICIO,
        INICIO + timedelta(hours=1),
        INICIO + timedelta(hours=2),
        INICIO + timedelta(hours=3),
    ) is False


# VERIFICACIÓN DE ASIGNABILIDAD

def test_equipo_disponible_y_sin_conflictos_es_asignable():
    equipo = crear_equipo()

    verificar_asignable(equipo, [], False)


def test_equipo_inactivo_no_es_asignable():
    equipo = crear_equipo(activo=False)

    with pytest.raises(ReglaNegocioError) as exc:
        verificar_asignable(equipo, [], False)

    assert str(exc.value) == f"El equipo {equipo.codigo} está desactivado"


@pytest.mark.parametrize(
    "estado, mensaje",
    [
        (
            EstadoEquipo.fuera_de_servicio,
            "está fuera de servicio",
        ),
        (
            EstadoEquipo.en_mantenimiento,
            "está en mantenimiento",
        ),
    ],
)
def test_equipo_con_estado_no_disponible_no_es_asignable(estado, mensaje):
    equipo = crear_equipo(estado=estado)

    with pytest.raises(ReglaNegocioError) as exc:
        verificar_asignable(equipo, [], False)

    assert str(exc.value) == f"El equipo {equipo.codigo} {mensaje}"


def test_equipo_con_asignaciones_en_conflicto_no_es_asignable():
    equipo = crear_equipo()

    with pytest.raises(ReglaNegocioError) as exc:
        verificar_asignable(equipo, [10, 20], False)

    assert str(exc.value) == (
        f"El equipo {equipo.codigo} ya tiene una asignación "
        "que se cruza con el periodo solicitado"
    )
    assert exc.value.info == {
        "asignaciones_en_conflicto": [10, 20]
    }


def test_equipo_con_mantenimiento_cruzado_no_es_asignable():
    equipo = crear_equipo()

    with pytest.raises(ReglaNegocioError) as exc:
        verificar_asignable(equipo, [], True)

    assert str(exc.value) == (
        f"El equipo {equipo.codigo} tiene un mantenimiento "
        "que se cruza con el periodo"
    )


# DERIVACIÓN DEL ESTADO OPERATIVO

def test_derivar_estado_con_mantenimiento_abierto():
    assert derivar_estado(1, 0) == EstadoEquipo.en_mantenimiento


def test_derivar_estado_con_incidente_grave_abierto():
    assert derivar_estado(0, 1) == EstadoEquipo.fuera_de_servicio


def test_derivar_estado_sin_mantenimiento_ni_incidentes():
    assert derivar_estado(0, 0) == EstadoEquipo.disponible


def test_mantenimiento_tiene_prioridad_sobre_incidente_grave():
    assert derivar_estado(1, 1) == EstadoEquipo.en_mantenimiento


# TRANSICIONES DE INCIDENTES

@pytest.mark.parametrize(
    "actual, nuevo",
    [
        (EstadoIncidente.abierto, EstadoIncidente.en_atencion),
        (EstadoIncidente.abierto, EstadoIncidente.resuelto),
        (EstadoIncidente.en_atencion, EstadoIncidente.resuelto),
    ],
)
def test_transiciones_permitidas(actual, nuevo):
    validar_transicion(actual, nuevo)


@pytest.mark.parametrize(
    "actual, nuevo",
    [
        (EstadoIncidente.abierto, EstadoIncidente.abierto),
        (EstadoIncidente.en_atencion, EstadoIncidente.abierto),
        (EstadoIncidente.en_atencion, EstadoIncidente.en_atencion),
        (EstadoIncidente.resuelto, EstadoIncidente.abierto),
        (EstadoIncidente.resuelto, EstadoIncidente.en_atencion),
        (EstadoIncidente.resuelto, EstadoIncidente.resuelto),
    ],
)
def test_transiciones_no_permitidas(actual, nuevo):
    with pytest.raises(ReglaNegocioError) as exc:
        validar_transicion(actual, nuevo)

    mensaje_esperado = (
        f"Transición no permitida: {actual.value} → {nuevo.value}"
    )

    assert str(exc.value) == mensaje_esperado