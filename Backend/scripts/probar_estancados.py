"""Prueba el endpoint de productos estancados."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))

from Backend.conexion_base import db

datos = db.obtener_productos_estancados(limite=10)
for d in datos:
    print(f'{d["id_producto"]}: {d["nombre"][:40]:40s} vendido={d["total_vendido"]}')
print(f"Total: {len(datos)} productos")
