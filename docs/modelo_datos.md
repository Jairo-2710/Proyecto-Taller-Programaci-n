# Modelo de datos

```mermaid
erDiagram
    ZONAS ||--o{ EQUIPOS : contiene
    EQUIPOS ||--o{ ASIGNACIONES : "se asigna en"
    EQUIPOS ||--o{ INCIDENTES : presenta
    EQUIPOS ||--o{ MANTENIMIENTOS : recibe
    INCIDENTES ||--o{ MANTENIMIENTOS : "origina (opcional)"
    USUARIOS ||--o{ ASIGNACIONES : registra
    USUARIOS ||--o{ INCIDENTES : reporta
    USUARIOS ||--o{ MANTENIMIENTOS : "es responsable de"
    USUARIOS ||--o{ AUDITORIA : genera

    ZONAS { int id PK
            string nombre UK
            string descripcion }
    EQUIPOS { int id PK
              string codigo UK
              string tipo "all_in_one | portatil"
              int zona_id FK
              int ram_gb
              int almacenamiento_gb
              json software
              string estado "disponible | en_mantenimiento | fuera_de_servicio"
              bool activo }
    ASIGNACIONES { int id PK
                   int equipo_id FK
                   int usuario_id FK
                   string actividad
                   datetime inicio
                   datetime fin
                   string estado "activa | cancelada"
                   string grupo }
    INCIDENTES { int id PK
                 int equipo_id FK
                 string severidad "baja | media | alta | critica"
                 string estado "abierto | en_atencion | resuelto"
                 text acciones
                 datetime fecha_reporte
                 datetime fecha_cierre }
    MANTENIMIENTOS { int id PK
                     int equipo_id FK
                     int incidente_id FK
                     string tipo "preventivo | correctivo"
                     datetime inicio
                     datetime fin "NULL = abierto" }
    USUARIOS { int id PK
               string email UK
               string password_hash
               string rol
               bool activo }
    AUDITORIA { int id PK
                int usuario_id FK
                string accion
                string entidad
                datetime fecha }
```

Notas de diseño:

- `estado` del equipo se **deriva** de incidentes graves abiertos y mantenimientos abiertos (`app/services/equipos.py`).
- `activo = false` es la baja lógica: el equipo conserva su historial (trazabilidad).
- `asignaciones.grupo` agrupa las asignaciones creadas por una misma solicitud de varios equipos.
