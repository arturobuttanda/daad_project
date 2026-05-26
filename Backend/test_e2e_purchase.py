import requests
import sys

BASE = "http://127.0.0.1:8002"

try:
    r = requests.get(f"{BASE}/api/cliente/productos")
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        print("ERROR: No hay productos disponibles para cliente.")
        sys.exit(2)
    product_id = items[0]["id_producto"]
    print("Producto seleccionado:", product_id)

    login = requests.post(
        f"{BASE}/api/auth/login",
        json={"correo": "cliente_demo_01@demo.local", "contrasena": "Demo1234"},
        timeout=10,
    )
    login.raise_for_status()
    client = login.json()
    client_id = client.get("id")
    print("Cliente demo id:", client_id)

    payload = {
        "id_cliente": client_id,
        "items": [{"id_producto": product_id, "cantidad": 1}],
    }
    purchase = requests.post(f"{BASE}/api/cliente/compras", json=payload, timeout=20)
    print("Respuesta compra:", purchase.status_code)
    print(purchase.text)
except Exception as e:
    print("ERROR E2E:", e)
    sys.exit(10)
