"""Carga equipos de demostración para probar la API.

Uso (desde la raíz del proyecto, con el entorno virtual activo):
    python -m scripts.seed_demo --aio 20 --portatiles 5

Las cantidades reales (≈80-100 All-in-One y ≈20 portátiles) deben confirmarse
en el levantamiento de información; este script solo genera datos de prueba.
"""
import argparse

from sqlalchemy import select

from app.domain.shared.enums import TipoEquipo
from app.infrastructure.persistence.bootstrap import init_db
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.orm import EquipoORM as Equipo, ZonaORM as Zona


def main(aio: int, portatiles: int) -> None:
    init_db()
    with SessionLocal() as db:
        zonas = {z.nombre: z.id for z in db.scalars(select(Zona))}
        lotes = [
            ("AIO", aio, TipoEquipo.all_in_one, zonas["Sala All-in-One"], 16, ["Python", "VS Code", "PostgreSQL"]),
            ("PRT", portatiles, TipoEquipo.portatil, zonas["Sala Portátiles"], 8, ["Python", "VS Code"]),
        ]
        creados = 0
        for prefijo, cantidad, tipo, zona_id, ram, software in lotes:
            for n in range(1, cantidad + 1):
                codigo = f"{prefijo}-{n:03d}"
                if db.scalar(select(Equipo.id).where(Equipo.codigo == codigo)):
                    continue
                db.add(
                    Equipo(
                        codigo=codigo,
                        tipo=tipo,
                        zona_id=zona_id,
                        ram_gb=ram,
                        almacenamiento_gb=512,
                        software=software,
                    )
                )
                creados += 1
        db.commit()
    print(f"Equipos creados: {creados}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aio", type=int, default=10)
    parser.add_argument("--portatiles", type=int, default=5)
    args = parser.parse_args()
    main(args.aio, args.portatiles)
