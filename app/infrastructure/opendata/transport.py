"""Transporte HTTP hacia las APIs públicas (biblioteca estándar, sin dependencias nuevas)."""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol


class ErrorTransitorio(Exception):
    """Fallo que puede desaparecer solo: red, timeout, 429 o 5xx. Se reintenta y cuenta para el breaker."""


class ErrorPermanente(Exception):
    """Fallo que reintentar no arregla (404 por un dataset mal escrito, 400, 403...)."""


class TransporteHttp(Protocol):
    def get_json(self, url: str, parametros: dict[str, str], encabezados: dict[str, str], timeout_s: float) -> Any: ...


class TransporteUrllib:
    def get_json(self, url: str, parametros: dict[str, str], encabezados: dict[str, str], timeout_s: float) -> Any:
        completa = f"{url}?{urllib.parse.urlencode(parametros)}" if parametros else url
        peticion = urllib.request.Request(completa, headers=encabezados, method="GET")
        try:
            with urllib.request.urlopen(peticion, timeout=timeout_s) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in (408, 425, 429) or error.code >= 500:
                raise ErrorTransitorio(f"HTTP {error.code} en {url}") from error
            raise ErrorPermanente(f"HTTP {error.code} en {url}") from error
        except json.JSONDecodeError as error:
            raise ErrorTransitorio(f"Respuesta no es JSON válido ({url})") from error
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            raise ErrorTransitorio(f"No se pudo conectar con {url}: {error}") from error
