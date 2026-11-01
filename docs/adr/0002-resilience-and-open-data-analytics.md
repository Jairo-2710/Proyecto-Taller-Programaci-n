# ADR 0002: Resilience for public APIs and DuckDB for analytics

- Status: Accepted
- Date: 2026-10-31

## Context
The system consumes public Colombian APIs (datos.gov.co and DANE, both Socrata/SODA). They can be slow,
rate-limited or down, and one failing source must not break the whole analysis or the rest of the API.

## Decision
- Each source has its own three-state circuit breaker (CLOSED, OPEN, HALF_OPEN): after N consecutive
  transient failures it opens and rejects calls immediately; after a recovery time it lets one probe call through.
- Retry with exponential backoff and jitter (0.5 s, 1 s, 2 s...) wraps the breaker. Only transient errors
  (timeouts, 5xx, 429) are retried and counted; permanent errors (4xx) are neither.
- If a source fails, the last good response is returned flagged `desde_cache=true`; if there is none, a 503 is raised.
- JSON responses and the system's own data are analysed with SQL in an in-memory DuckDB (`read_json_auto`),
  using descriptive statistics (AVG, MEDIAN, STDDEV_SAMP, QUANTILE_CONT). DuckDB sits behind the `MotorAnalitico` port.
- The HTTP transport is a port too, so tests use fake transports and a fake clock.

## Consequences
- A failing API degrades the answer instead of breaking it, and breaker state is visible at `/datos-abiertos/estado` and `/ui`.
- Breaker state is per process and in memory; with several workers each has its own state.
- Dataset ids are configurable by environment variables because column names can change; a tolerant
  normalisation maps them to a fixed schema.
- DuckDB adds a dependency but avoids pandas and extra servers for analytical queries.
