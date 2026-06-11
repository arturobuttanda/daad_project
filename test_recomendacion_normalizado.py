#!/usr/bin/env python3
"""Test de recomendación de precios con normalización de acentos."""

from fastapi.testclient import TestClient
from Backend.app import app

client = TestClient(app)

# Test casos
casos = [
    {
        "nombre": "audifonos sin acento",
        "payload": {
            "id_producto": "TEST001",
            "nombre": "audifonos",
            "marca": "samsung",
            "categoria": "electronics",
        }
    },
    {
        "nombre": "audífonos con acento",
        "payload": {
            "id_producto": "TEST002",
            "nombre": "audífonos",
            "marca": "samsung",
            "categoria": "electronics",
        }
    },
    {
        "nombre": "AUDIFONOS mayúsculas",
        "payload": {
            "id_producto": "TEST003",
            "nombre": "AUDIFONOS",
            "marca": "SAMSUNG",
            "categoria": "ELECTRONICS",
        }
    },
    {
        "nombre": "Marca y categoría con acentos y espacios",
        "payload": {
            "id_producto": "TEST004",
            "nombre": "AudífónoS inalámbricos",
            "marca": "SamSúng  ",
            "categoria": "Electrónica ",
        }
    }
]

def es_producto_audifonos(producto):
    nombre = str(producto.get("nombre") or "").lower()
    categoria = str(producto.get("categoria") or "").lower()
    return "audif" in nombre or "audif" in categoria or "audio" in categoria

print("\n" + "=" * 70)
print("TEST: Normalización de acentos en recomendación de precios")
print("=" * 70)

for caso in casos:
    print(f"\n{caso['nombre']}:")
    print("-" * 70)
    
    response = client.post("/api/productos/recomendacion-precio", json=caso["payload"])
    
    if response.status_code == 200:
        datos = response.json()
        precio = datos.get('suggested_price')
        similares = len(datos.get('similar_products', []))
        similares_audifonos = [p for p in datos.get('similar_products', []) if es_producto_audifonos(p)]
        
        print(f"  ✓ Status: {response.status_code}")
        print(f"  💰 Precio sugerido: ${precio}")
        print(f"  🎯 Productos similares encontrados: {similares}")
        print(f"  🎧 Similares de tipo audífonos detectados: {len(similares_audifonos)}")
        
        if similares > 0:
            print(f"  📝 Top 3 similares:")
            for i, prod in enumerate(datos.get('similar_products', [])[:3], 1):
                sim_pct = (prod.get('similarity_score', 0) * 100)
                print(f"     {i}. {prod.get('nombre')[:50]:50s} | ${prod.get('precio_actual'):>8.2f} | {sim_pct:>5.1f}%")
        if caso['nombre'].startswith('Aud'):
            assert len(similares_audifonos) > 0, f"No se detectaron similares de tipo audífonos para {caso['nombre']}"
    else:
        print(f"  ✗ Error {response.status_code}: {response.text}")

print("\n" + "=" * 70)
print("✅ Test completado")
print("=" * 70 + "\n")
