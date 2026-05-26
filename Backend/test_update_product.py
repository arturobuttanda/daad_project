import requests
BASE = "http://127.0.0.1:8002"
product_id = "B071J4KHDQ"
url = f"{BASE}/api/productos/{product_id}"
payload = {"precio_actual": 2.49, "stock": 10}
try:
    r = requests.put(url, json=payload, timeout=10)
    print(r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
except Exception as e:
    print('ERROR', e)
