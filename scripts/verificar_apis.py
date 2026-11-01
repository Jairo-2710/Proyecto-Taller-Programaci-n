"""Comprueba desde TU computador que las dos APIs públicas responden y muestra sus columnas.

    python -m scripts.verificar_apis
"""
from app import config
from app.infrastructure.opendata.transport import TransporteUrllib

for nombre, base, dataset in (
    ("datos.gov.co", config.DATOS_GOV_BASE_URL, config.DATOS_GOV_DATASET_ID),
    ("DANE", config.DANE_BASE_URL, config.DANE_DATASET_ID),
):
    url = f"{base.rstrip('/')}/resource/{dataset}.json"
    try:
        filas = TransporteUrllib().get_json(url, {"$limit": "3"}, {"Accept": "application/json"}, 10.0)
        print(f"[OK] {nombre}: {url}\n     columnas: {sorted(filas[0]) if filas else '(sin filas)'}")
    except Exception as e:  # noqa: BLE001
        print(f"[FALLA] {nombre}: {url}\n     {e}")
