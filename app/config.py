"""Configuración central. Todo se puede sobrescribir con variables de entorno.

Solo la capa de infraestructura y el punto de composición (api/container.py) leen este módulo;
el dominio y la aplicación reciben sus parámetros por constructor.
"""
import os
from datetime import datetime, timedelta, timezone

APP_NAME = "Sistema Inteligente de Gestión y Optimización de Recursos Tecnológicos Universitarios"
APP_VERSION = "0.2.0"

# Base de datos: SQLite para desarrollo; PostgreSQL en producción, por ejemplo
# DATABASE_URL=postgresql+psycopg2://usuario:clave@localhost:5432/recursos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recursos_tecnologicos.db")

# Seguridad (JWT). Cambiar SECRET_KEY fuera de desarrollo.
SECRET_KEY = os.getenv("SECRET_KEY", "clave-solo-para-desarrollo-cambiar-en-produccion-0123456789")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))

# Administrador inicial (se crea solo si no existe ningún usuario)
ADMIN_NOMBRE = os.getenv("ADMIN_NOMBRE", "Administrador")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@umb.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin12345!")

# Reglas de negocio y parámetros del análisis (ajustables tras el levantamiento de información)
HORAS_OPERATIVAS_DIA = float(os.getenv("HORAS_OPERATIVAS_DIA", "14"))  # p. ej. 7:00 a 21:00
MAX_HORAS_ASIGNACION = float(os.getenv("MAX_HORAS_ASIGNACION", "12"))
UMBRAL_UTILIZACION_ALTA = float(os.getenv("UMBRAL_UTILIZACION_ALTA", "0.80"))
UMBRAL_UTILIZACION_BAJA = float(os.getenv("UMBRAL_UTILIZACION_BAJA", "0.10"))
UMBRAL_ZONA_BAJA = float(os.getenv("UMBRAL_ZONA_BAJA", "0.30"))
INCIDENTES_PARA_REVISION = int(os.getenv("INCIDENTES_PARA_REVISION", "3"))
DIAS_MANTENIMIENTO_PROLONGADO = int(os.getenv("DIAS_MANTENIMIENTO_PROLONGADO", "7"))
MIN_ASIGNACIONES_ANALISIS = int(os.getenv("MIN_ASIGNACIONES_ANALISIS", "10"))
MIN_DIAS_PERIODO_ANALISIS = int(os.getenv("MIN_DIAS_PERIODO_ANALISIS", "7"))

# --- APIs públicas colombianas (ambas exponen la API SODA de Socrata)
# Los identificadores de dataset se pueden cambiar sin tocar el código. Por defecto ambas fuentes
# apuntan a DIVIPOLA (códigos de municipios, producto del DANE publicado en datos.gov.co).
DATOS_GOV_BASE_URL = os.getenv("DATOS_GOV_BASE_URL", "https://www.datos.gov.co")
DATOS_GOV_DATASET_ID = os.getenv("DATOS_GOV_DATASET_ID", "gdxc-w37w")
DANE_BASE_URL = os.getenv("DANE_BASE_URL", "https://www.datos.gov.co")
DANE_DATASET_ID = os.getenv("DANE_DATASET_ID", "gdxc-w37w")
SOCRATA_APP_TOKEN = os.getenv("SOCRATA_APP_TOKEN", "")  # opcional: sube el límite de peticiones
OPENDATA_LIMITE_REGISTROS = int(os.getenv("OPENDATA_LIMITE_REGISTROS", "2000"))
OPENDATA_TIMEOUT_S = float(os.getenv("OPENDATA_TIMEOUT_S", "10"))

# --- Resiliencia
BREAKER_UMBRAL_FALLOS = int(os.getenv("BREAKER_UMBRAL_FALLOS", "3"))
BREAKER_RECUPERACION_S = float(os.getenv("BREAKER_RECUPERACION_S", "30"))
RETRY_INTENTOS = int(os.getenv("RETRY_INTENTOS", "3"))
RETRY_BASE_S = float(os.getenv("RETRY_BASE_S", "0.5"))

# Colombia no usa horario de verano: UTC-5 fijo.
COL_TZ = timezone(timedelta(hours=-5))


def ahora() -> datetime:
    """Hora actual de Colombia, sin zona horaria (así se guarda en la base de datos)."""
    return datetime.now(COL_TZ).replace(tzinfo=None)
