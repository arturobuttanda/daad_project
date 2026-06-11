#!/usr/bin/env python3
from fastapi.testclient import TestClient
from Backend.app import app

client = TestClient(app)

response = client.post('/api/productos/recomendacion-precio', json={
    'nombre': 'Audifonos galaxy 4 pro',
    'marca': 'Galaxy',
    'categoria': 'Electronics',
})

if response.status_code != 200:
    print(f'Error {response.status_code}: {response.text}')
else:
    data = response.json()
    print('\n=== FILTRO TIPO EXCEL ===\n')
    print('Precio sugerido: $' + str(data.get('suggested_price')))
    print('\nTop 10 similares:\n')
    for i, p in enumerate(data.get('similar_products', [])[:10], 1):
        nombre = str(p.get('nombre', ''))[:55]
        sim = p.get('similarity_score', 0)*100
        print(f'{i:2d}. {nombre:55s} | {sim:5.1f}%')
