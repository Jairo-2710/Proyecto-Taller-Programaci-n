# Proyecto-Taller-Programacion

**Sistema Inteligente de Gestión y Optimización de Recursos Tecnológicos Universitarios**

Ingeniería de Software · Universidad Manuela Beltrán · Taller de Programación
Autor: Jairo Esteban Ojeda Ramirez

## Repositorio

Dentro de este repositorio se desarrolla el proyecto final de la asignatura Taller de Programación: se guarda y organiza cada avance a lo largo del semestre, aplicando los conceptos y habilidades de la materia para entregar un producto mínimo viable (MVP). El repositorio es el lugar de control de versiones y desarrollo.

## Descripción del proyecto

API REST que centraliza la información de los computadores de las salas tecnológicas (escenario inicial estimado: ~80-100 All-in-One y ~20 portátiles, por confirmar en el levantamiento de información) y permite:

- **Inventario:** registrar, consultar, actualizar y desactivar equipos con código único, tipo, zona, características y estado.
- **Disponibilidad y asignaciones:** consultar equipos libres en un periodo, asignarlos sin cruces de horario y validar requisitos (tipo, RAM, almacenamiento, software).
- **Incidentes y mantenimiento:** registrar fallas, controlar su atención y mantener el historial; un equipo con falla grave o en mantenimiento no se asigna.
- **Análisis y optimización:** indicadores de utilización y demanda, y recomendaciones por reglas de decisión (sin IA compleja, como define el alcance).
- **Seguridad:** autenticación JWT, roles y registro de auditoría.

## Objetivos del proyecto

- Desarrollar y entregar un software funcional o producto mínimo viable.
- Mejorar las habilidades de solución de problemas y de desarrollo de software.

## Enfoque de desarrollo

El proyecto se realiza de forma iterativa e incremental durante el semestre, siguiendo la metodología Scrum:

1. **Product Backlog and Goal setting:** se define el alcance del producto, sus requerimientos y los sprints para cada etapa de desarrollo.
2. **Sprint Planning:** se organizan los temas de cada sprint, estableciendo trazabilidad y una línea de tiempo clara.
3. **Sprint Execution:** implementación de las funcionalidades.
4. **Continuous Integration:** se integran las partes del código para asegurar su sincronización y estabilidad.
5. **Quality Assurance:** validación y verificación mediante revisiones, depuración y ciclos de pruebas.
6. **Analysis:** documentación de especificaciones técnicas, registros del desarrollo y análisis crítico de la eficiencia del producto.
7. **MVP Delivery:** entrega del producto mínimo viable funcional para su evaluación al final del semestre.

El proyecto sigue en desarrollo: los requerimientos y funcionalidades se agregan durante el semestre. Ver [`docs/backlog.md`](docs/backlog.md) y [`docs/modelo_datos.md`](docs/modelo_datos.md).

## Estructura del repositorio

```
Proyecto-Taller-Programacion/
├── main.py                 # Punto de entrada FastAPI (uvicorn main:app)
├── requirements.txt        # Dependencias con versiones fijas
├── setup.bat               # Crea .venv, instala librerías y genera __pycache__ (Windows)
├── pytest.ini
├── .env.example            # Variables de entorno de ejemplo
├── .gitignore
├── app/
│   ├── config.py           # Configuración y parámetros
│   ├── domain/             # Entidades, políticas y puertos (sin frameworks), por contexto:
│   │                       #   identidad · inventario · asignaciones · mantenimiento · analitica · shared
│   ├── application/        # Casos de uso con inyección de dependencias por constructor
│   ├── infrastructure/     # Adaptadores: persistence (SQLAlchemy), security, resilience
│   │                       #   (circuit breaker + retry), opendata (datos.gov.co/DANE), analytics (DuckDB)
│   └── api/                # Routers FastAPI, schemas, composition root (container.py) y panel /ui
├── tests/                  # Pruebas con pytest
├── scripts/seed_demo.py    # Datos de demostración
└── docs/                   # Backlog, modelo de datos y ADR (docs/adr, en inglés)
```

## Arquitectura hexagonal (Guía 6)

`api → application → domain ← infrastructure`: el dominio no importa frameworks (lo verifica `tests/test_arquitectura.py`). Ver [ADR 0001](docs/adr/0001-hexagonal-architecture-and-bounded-contexts.md) y [ADR 0002](docs/adr/0002-resilience-and-open-data-analytics.md).

- **APIs públicas:** datos.gov.co y DANE (SODA) con circuit breaker de 3 estados (CLOSED/OPEN/HALF_OPEN) y retry con backoff exponencial. Por defecto ambas usan el dataset DIVIPOLA `gdxc-w37w`; se cambian con `DATOS_GOV_DATASET_ID` / `DANE_DATASET_ID` (ver `.env.example`). Verifica desde tu PC: `python -m scripts.verificar_apis`.
- **DuckDB:** `/analitica/equipos`, `/analitica/asignaciones`, `/datos-abiertos/analisis` (SQL con promedio, mediana, desviación y percentiles).
- **Panel web:** http://127.0.0.1:8000/ui (login + gráficas + estado del circuit breaker).
- **CI:** `.github/workflows/ci.yml` ejecuta `pytest` en cada push.

El `.venv/` y los `__pycache__/` no se suben a GitHub (están en `.gitignore`); se regeneran con `setup.bat`.

## Puesta en marcha (Windows)

```bat
setup.bat
.venv\Scripts\activate
uvicorn main:app --reload
```

Equivalente manual:

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

- Documentación interactiva (OpenAPI 3): <http://127.0.0.1:8000/docs>
- Administrador inicial (solo desarrollo): `admin@umb.local` / `Admin12345!`. Cámbielo con las variables `ADMIN_EMAIL` y `ADMIN_PASSWORD` (ver `.env.example`) y defina `SECRET_KEY` propia.
- Datos de demostración: `python -m scripts.seed_demo --aio 20 --portatiles 5`
- Base de datos: SQLite por defecto; para PostgreSQL defina `DATABASE_URL=postgresql+psycopg2://usuario:clave@host:5432/base`.

Flujo básico en `/docs`: `POST /auth/login` → copiar el `access_token` → botón **Authorize** → probar los endpoints.

## Pruebas

```bat
python -m pytest
```

24 pruebas cubren autenticación, permisos por rol, validación de datos, unicidad de códigos, conflictos de horario, equipos fuera de servicio, flujo de incidentes y mantenimientos, cálculo de indicadores y recomendaciones.

## Roles y permisos

| Operación | administrador | encargado_sala | soporte | docente | coordinador |
|---|:-:|:-:|:-:|:-:|:-:|
| Consultar equipos, zonas y disponibilidad | ✓ | ✓ | ✓ | ✓ | ✓ |
| Crear/editar/desactivar equipos y zonas; usuarios; auditoría | ✓ | | | | |
| Crear/cancelar asignaciones y solicitudes | ✓ | ✓ | | | |
| Consultar historial de asignaciones | ✓ | ✓ | | ✓ | ✓ |
| Reportar un incidente | ✓ | ✓ | ✓ | ✓ | ✓ |
| Consultar incidentes, mantenimientos e historial del equipo | ✓ | ✓ | ✓ | | ✓ |
| Atender incidentes y gestionar mantenimientos | ✓ | | ✓ | | |
| Indicadores y recomendaciones | ✓ | ✓ | ✓ | | ✓ |

## Endpoints principales

| Módulo | Endpoints |
|---|---|
| Autenticación | `POST /auth/login`, `GET /auth/me` |
| Usuarios | `POST/GET /usuarios`, `PATCH /usuarios/{id}`, `GET /auditoria` |
| Inventario | `GET/POST /zonas`; `GET/POST /equipos`, `GET/PATCH/DELETE /equipos/{id}` (DELETE = baja lógica), `GET /equipos/{id}/historial` |
| Disponibilidad | `GET /equipos/disponibles?inicio=&fin=&zona_id=&tipo=&ram_min=&software=` |
| Asignaciones | `POST /asignaciones`, `POST /asignaciones/sugerencia`, `POST /asignaciones/solicitud`, `GET /asignaciones`, `PATCH /asignaciones/{id}/cancelar` |
| Incidentes | `POST/GET /incidentes`, `GET/PATCH /incidentes/{id}` |
| Mantenimiento | `POST/GET /mantenimientos`, `PATCH /mantenimientos/{id}/cerrar` |
| Análisis | `GET /analisis/resumen`, `/utilizacion`, `/demanda`, `/incidentes`, `/recomendaciones` |

## Reglas de negocio

- Un equipo no puede tener dos asignaciones activas con periodos que se crucen (periodos contiguos sí se permiten).
- No se asignan equipos desactivados, en mantenimiento ni fuera de servicio.
- Un incidente de severidad **alta** o **crítica** deja el equipo `fuera_de_servicio` hasta que se resuelva; un mantenimiento abierto lo deja `en_mantenimiento`. El estado del equipo se deriva de estos registros, no se edita a mano.
- Un incidente avanza `abierto → en_atencion → resuelto`; para resolverlo deben registrarse las acciones realizadas.
- Iniciar un mantenimiento no cancela asignaciones futuras: las lista en `asignaciones_afectadas` para que el personal las reubique.
- Una solicitud de varios equipos es "todo o nada" y prioriza la zona pedida; solo usa otras zonas si se autoriza (`permitir_otras_zonas`). `POST /asignaciones/sugerencia` muestra la selección sin crearla.
- Entre equipos compatibles se prefieren los de menor uso histórico, para repartir el desgaste.
- Las fechas se guardan en hora de Colombia (UTC-5); si el cliente envía zona horaria, se convierte.

## Indicador de utilización

```
utilización = horas de asignación activa dentro del periodo
              / (días del periodo × HORAS_OPERATIVAS_DIA)        (tope 1.0)
```

`HORAS_OPERATIVAS_DIA` (por defecto 14, p. ej. 7:00-21:00) y los umbrales (alta ≥ 80 %, baja < 10 %, zona con baja demanda < 30 %) son parámetros de `app/config.py` que deben validarse con la universidad. Las recomendaciones solo buscan patrones de demanda si hay al menos 10 asignaciones y un periodo de 7 días; en caso contrario lo indican en lugar de inventar conclusiones.

## Limitaciones conocidas y siguientes pasos

- La verificación de cruces se hace en la aplicación; con varias instancias y PostgreSQL conviene reforzarla con una restricción de exclusión a nivel de base de datos.
- Las tablas se crean con `create_all`; para evolucionar el esquema en producción se recomienda Alembic.
- La interfaz de usuario (HTML/CSS/JS) es opcional según la propuesta y no está incluida.
- No hay integración con autenticación institucional (fuera del alcance inicial).

## Referencias (APA 7.ª edición)

Congreso de Colombia. (2012, 17 de octubre). *Ley Estatutaria 1581 de 2012, por la cual se dictan disposiciones generales para la protección de datos personales*. Diario Oficial No. 48.587. https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981

pytest-dev. (s. f.). *pytest documentation*. https://docs.pytest.org/

Pydantic. (s. f.). *Pydantic documentation*. https://docs.pydantic.dev/

PyJWT. (s. f.). *PyJWT documentation*. https://pyjwt.readthedocs.io/

PostgreSQL Global Development Group. (s. f.). *PostgreSQL documentation*. https://www.postgresql.org/docs/

Python Software Foundation. (s. f.). *Python documentation*. https://docs.python.org/3/

Ramírez, S. (s. f.). *FastAPI documentation*. https://fastapi.tiangolo.com/

SQLAlchemy. (s. f.). *SQLAlchemy documentation*. https://docs.sqlalchemy.org/
