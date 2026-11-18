"""Agrega equipos de demostración al inventario.

Los 20 equipos iniciales (15 All-in-One y 5 portátiles) ya se cargan solos al arrancar la API con la
base de datos vacía. Use este script solo para agregar más:

    python -m scripts.seed_demo --aio 30 --portatiles 10

Los códigos ya existentes (AIO-001, PRT-001…) se respetan, de modo que se puede ejecutar varias
veces sin duplicar equipos; solo se crean los que faltan.

Las cantidades reales (≈80-100 All-in-One y ≈20 portátiles) deben confirmarse en el levantamiento
de información; este script solo genera datos de prueba.
"""
import argparse

from app.infrastructure.persistence.bootstrap import init_db
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.demo_data import cargar_equipos


def main(aio: int, portatiles: int) -> None:
    init_db()
    with SessionLocal() as db:
        creados = cargar_equipos(db, aio, portatiles)
        db.commit()
    print(f"Equipos creados: {creados}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aio", type=int, default=10, help="cantidad total de All-in-One que debe haber")
    parser.add_argument("--portatiles", type=int, default=5, help="cantidad total de portátiles que debe haber")
    args = parser.parse_args()
    main(args.aio, args.portatiles)
