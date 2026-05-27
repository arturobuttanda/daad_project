from pathlib import Path
import os
from dotenv import load_dotenv
import oracledb

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

DB_USER = os.environ['DB_USER']
DB_PASSWORD = os.environ['DB_PASSWORD']
DB_DSN = os.environ['DB_DSN']
WALLET_PATH = os.environ.get('WALLET_PATH') or os.environ.get('WALLET_LOCATION')
WALLET_PASSWORD = os.environ.get('WALLET_PASSWORD','')

if not WALLET_PATH:
    _wallet_root = ROOT / 'wallet'
    if _wallet_root.is_dir():
        for _child in sorted(_wallet_root.iterdir()):
            if _child.is_dir() and (_child / 'tnsnames.ora').is_file():
                WALLET_PATH = str(_child)
                break

if not WALLET_PATH:
    raise RuntimeError('WALLET_PATH no definido en .env')

wallet_location = Path(WALLET_PATH)
if not wallet_location.is_absolute():
    wallet_location = (ROOT / wallet_location).resolve()


def get_conn():
    tns = wallet_location / 'tnsnames.ora'
    if tns.exists():
        # try to use tns alias if DB_DSN is present there
        content = tns.read_text(encoding='utf-8')
        # skip parsing complexity, fallback to DB_DSN
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        config_dir=str(wallet_location),
        wallet_location=str(wallet_location),
        wallet_password=WALLET_PASSWORD,
    )


with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id_venta, id_cliente, id_vendedor, fecha_venta, monto_total, total_unidades "
            "FROM ventas ORDER BY fecha_venta DESC FETCH NEXT 10 ROWS ONLY"
        )
        rows = cur.fetchall()
        if not rows:
            print('No hay ventas en la base de datos.')
        for r in rows:
            print('VENTA:', r[0], '| cliente:', r[1], '| vendedor:', r[2], '| fecha:', r[3], '| monto:', r[4], '| unidades:', r[5])
            cur.execute(
                "SELECT id_producto, cantidad, precio_unitario, subtotal FROM venta_detalle WHERE id_venta = :id_venta",
                {'id_venta': r[0]}
            )
            detalles = cur.fetchall()
            for d in detalles:
                print('  - DETALLE:', d[0], 'cant=', d[1], 'precio=', d[2], 'subtotal=', d[3])
            print()
