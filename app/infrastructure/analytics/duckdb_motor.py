"""Motor analítico con DuckDB: procesa datos JSON con SQL, en memoria."""
import json
import tempfile
from decimal import Decimal
from pathlib import Path

import duckdb


class DuckDbMotor:
    """Implementa el puerto `MotorAnalitico`.

    Cada lista de registros se escribe como un archivo JSON temporal y se carga con
    `read_json_auto`, lo que permite consultar la respuesta de una API como si fuera una tabla.
    """

    def ejecutar(self, tablas: dict[str, list[dict]], sql: str) -> list[dict]:
        con = duckdb.connect(":memory:")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                for nombre, filas in tablas.items():
                    if not nombre.isidentifier():
                        raise ValueError(f"Nombre de tabla inválido: {nombre!r}")
                    ruta = Path(tmp) / f"{nombre}.json"
                    ruta.write_text(json.dumps(filas, default=str), encoding="utf-8")
                    con.execute(f'CREATE TABLE "{nombre}" AS SELECT * FROM read_json_auto(?)', [str(ruta)])
                cursor = con.execute(sql)
                columnas = [d[0] for d in cursor.description]
                return [
                    {c: (float(v) if isinstance(v, Decimal) else v) for c, v in zip(columnas, fila)}
                    for fila in cursor.fetchall()
                ]
        finally:
            con.close()
