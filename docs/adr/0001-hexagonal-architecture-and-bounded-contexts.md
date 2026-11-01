# ADR 0001: Hexagonal architecture and DDD bounded contexts

- Status: Accepted
- Date: 2026-10-31

## Context
The system manages university computers: inventory, assignments (no schedule conflicts), incidents and
maintenance, analytics. The first version mixed HTTP, SQLAlchemy and business rules in the same modules,
so rules could only be tested through the API and swapping a technology (database, external API) touched everything.

## Decision
Adopt hexagonal architecture (ports and adapters) with four layers:
- `domain`: entities, pure policies and ports (`typing.Protocol`). No framework imports.
- `application`: use-case services receiving their ports through the constructor (dependency injection).
- `infrastructure`: adapters (SQLAlchemy repositories, JWT, scrypt, circuit breaker, Socrata clients, DuckDB).
- `api`: FastAPI routers, schemas and the composition root (`container.py`), the only place that wires adapters to ports.

Split the domain into bounded contexts: identidad, inventario, asignaciones, mantenimiento, analitica,
plus a small shared kernel (enums, errors, ports). Contexts talk through ports, not each other's tables.
A test (`tests/test_arquitectura.py`) fails if `domain` or `application` import frameworks or outer layers.

## Consequences
- Business rules are unit-tested with `unittest.mock` doubles, with no database or network.
- Adapters can be replaced (e.g. PostgreSQL, another open-data source) without touching use cases.
- More files and mapping code (ORM row <-> entity) than a layered CRUD app; accepted for testability.
- The 24 original API tests were kept unchanged as a regression net during the refactor.
