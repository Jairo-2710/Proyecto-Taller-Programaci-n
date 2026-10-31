# Product Backlog y planificación de sprints

Cronograma de la propuesta (6 semanas) organizado en 3 sprints de 2 semanas.
Estado: ✅ implementado en el repositorio · 🔲 pendiente.

**Objetivo del producto (Product Goal):** un MVP que centralice el inventario, evite conflictos de asignación, dé seguimiento a incidentes y mantenimientos, y genere indicadores y recomendaciones verificables.

## Sprint 1 — Semanas 1-2: Fundamentos
| ID | Historia de usuario | Estado |
|---|---|---|
| HU-01 | Como equipo de desarrollo, quiero levantar requisitos y validar el proceso real con los responsables de las salas, para confirmar los problemas y las cantidades de equipos. | 🔲 |
| HU-02 | Como administrador, quiero iniciar sesión y que cada rol tenga permisos distintos, para proteger el inventario. | ✅ |
| HU-03 | Como administrador, quiero registrar, consultar, actualizar y desactivar equipos con código único, tipo, zona y características. | ✅ |
| HU-04 | Como personal de sala, quiero consultar el inventario por zona, tipo y estado. | ✅ |

## Sprint 2 — Semanas 3-4: Operación
| ID | Historia de usuario | Estado |
|---|---|---|
| HU-05 | Como docente, quiero consultar qué equipos están libres en un periodo y cumplen mis requisitos. | ✅ |
| HU-06 | Como encargado de sala, quiero asignar equipos sin cruces de horario y cancelar asignaciones. | ✅ |
| HU-07 | Como encargado de sala, quiero pedir N equipos para una actividad y que el sistema proponga los más adecuados, incluso de otra zona si lo autorizo. | ✅ |
| HU-08 | Como usuario, quiero reportar una falla; como soporte, quiero atenderla y registrar las acciones realizadas. | ✅ |
| HU-09 | Como soporte, quiero abrir y cerrar mantenimientos y que el equipo no se asigne mientras no esté operativo. | ✅ |
| HU-10 | Como administrador, quiero un registro de auditoría de las operaciones importantes. | ✅ |

## Sprint 3 — Semanas 5-6: Análisis, calidad y entrega
| ID | Historia de usuario | Estado |
|---|---|---|
| HU-11 | Como coordinador, quiero indicadores de utilización por equipo y de demanda por zona, día y hora. | ✅ |
| HU-12 | Como coordinador, quiero recomendaciones de redistribución y mantenimiento basadas en reglas y datos históricos. | ✅ |
| HU-13 | Como equipo, queremos pruebas automáticas de reglas de negocio, validación y permisos. | ✅ (24 pruebas) |
| HU-14 | Como equipo, queremos confirmar con la universidad los umbrales y las horas operativas del análisis. | 🔲 |
| HU-15 | Como equipo, queremos documentación técnica final y preparar la presentación. | 🔲 |

## Backlog por priorizar (opcional según tiempo)
- Interfaz web (HTML, CSS, JavaScript).
- Migraciones con Alembic y restricción de exclusión en PostgreSQL para cruces de horario.
- Colección de Postman exportada para la entrega.
- Ajustar la tabla de tecnologías de la propuesta (Flask → FastAPI) o justificar el cambio.

## Definición de terminado (DoD)
Código revisado, pruebas en verde (`python -m pytest`), endpoint documentado en `/docs` y cambios integrados en `main` mediante pull request.
