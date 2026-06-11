from fastapi.testclient import TestClient
from Backend.app import app

client = TestClient(app)
print('import ok')
print('client ok')

payload = {
    'id_producto': '234542',
    'nombre': 'Audifonos Galaxy Buds4 pro',
    'marca': 'Samsung',
    'categoria': 'Electronics',
    'precio_actual': 0.0,
    'stock': 0,
    'precio_fabricacion': 250,
    'fecha_caducidad': None,
    'imagen_url': None,
}

response = client.post('/api/productos/recomendacion-precio', json=payload)
print('status', response.status_code)
print(response.headers.get('content-type'))
print(response.text)
