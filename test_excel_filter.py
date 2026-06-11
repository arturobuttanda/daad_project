#!/usr/bin/env python3
"""Test del nuevo filtro tipo Excel."""

from fastapi.testclient import TestClient
from Backend.app import app

client = TestClient(app)

print("\n" + "=" * 80)
print("TEST: Filtro tipo Excel para 'Audifonos galaxy 4 pro'")
print("=" * 80 + "\n")

response = client.post('/api/productos/recomendacion-precio', json={
    'id_producto': 'TEST001',
    'nombre': 'Audifonos galaxy 4 pro',
    'marca': 'Galaxy',
    'categoria': 'Electronics',
})

if response.status_code == 200:
    data = response.json()
    print(f"✅ Precio sugerido: ${data.get('suggested_price')}")
    print(f"\nTop 10 similares:\n")
    for i, prod in enumerate(data.get('similar_products', [])[:10], 1):
        sim_pct = prod.get('similarity_score', 0) * 100
        nombre = str(prod.get('nombre', ''))[:60]
        marca = str(prod.get('marca', ''))[:15]
        print(f"{i:2d}. {nombre:60s} | {marca:15s} | {sim_pct:5.1f}%")
        
        # Advertencia si es TV
        if any(x in nombre.lower() for x in ['television', 'tv', 'pantalla']) and i <= 3:
            print(f"     ⚠️  TV en top 3 - Problema!")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
