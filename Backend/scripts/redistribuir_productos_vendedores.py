from __future__ import annotations

import os
import random
import secrets
import uuid
from dataclasses import dataclass
from pathlib import Path

import oracledb  # type: ignore[import-not-found]
from dotenv import load_dotenv
from passlib.context import CryptContext

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_PATH = os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION")
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

if not WALLET_PATH:
    _wallet_root = ROOT_DIR / "wallet"
    if _wallet_root.is_dir():
        for _child in sorted(_wallet_root.iterdir()):
            if _child.is_dir() and (_child / "tnsnames.ora").is_file():
                WALLET_PATH = str(_child)
                break

if not WALLET_PATH:
    raise RuntimeError("WALLET_PATH no definido en .env")

wallet_location = Path(WALLET_PATH)
if not wallet_location.is_absolute():
    wallet_location = (ROOT_DIR / wallet_location).resolve()

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
OUTPUT_TXT = ROOT_DIR / "vendedores_demo.txt"

FIRST_NAMES = [
    "Alberto",
    "Andrea",
    "Brenda",
    "Carlos",
    "Daniela",
    "Diego",
    "Elena",
    "Fernanda",
    "Gabriel",
    "Hector",
    "Isabel",
    "Javier",
    "Karen",
    "Luis",
    "Marta",
    "Nicolas",
]

LAST_NAMES = [
    "Aguilar",
    "Campos",
    "Cortes",
    "Flores",
    "Garcia",
    "Hernandez",
    "Lopez",
    "Mendoza",
    "Morales",
    "Navarro",
    "Paredes",
    "Ramirez",
    "Santos",
    "Torres",
    "Vega",
    "Zavala",
]

SPECIALTIES = ["Bebidas", "Despensa", "Tecnologia", "Hogar", "Belleza", "Limpieza", "Farmacia", "Accesorios"]


@dataclass(frozen=True)
class VendorAccount:
    id_usuario: str
    nombre: str
    telefono: str
    correo: str
    contrasena: str
    codigo_vendedor: str
    especialidad: str
    objetivo_ventas: float


def get_connection():
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        config_dir=str(wallet_location),
        wallet_location=str(wallet_location),
        wallet_password=WALLET_PASSWORD,
    )


def make_vendor_accounts(count: int = 10) -> list[VendorAccount]:
    rng = random.Random(20260525)
    accounts: list[VendorAccount] = []

    for index in range(1, count + 1):
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        second_last_name = rng.choice(LAST_NAMES)
        nombre = f"{first_name} {last_name} {second_last_name}"
        correo = f"vendedor_demo_{index:02d}@demo.local"
        contrasena = f"Vnd-{index:02d}-{secrets.token_hex(4)}"
        telefono = f"55{rng.randint(10000000, 99999999)}"
        codigo_vendedor = f"V-{3000 + index}"
        especialidad = rng.choice(SPECIALTIES)
        objetivo_ventas = float(rng.randint(80000, 220000))
        id_usuario = str(uuid.uuid5(uuid.NAMESPACE_URL, correo))

        accounts.append(
            VendorAccount(
                id_usuario=id_usuario,
                nombre=nombre,
                telefono=telefono,
                correo=correo,
                contrasena=contrasena,
                codigo_vendedor=codigo_vendedor,
                especialidad=especialidad,
                objetivo_ventas=objetivo_ventas,
            )
        )

    return accounts


def fetch_products(cursor):
    cursor.execute("SELECT id_producto FROM productos ORDER BY nombre, id_producto")
    return [row[0] for row in cursor.fetchall()]


def upsert_vendors(cursor, accounts: list[VendorAccount]) -> tuple[list[tuple[str, str, str]], list[str]]:
    credentials_rows: list[tuple[str, str, str]] = []
    vendor_ids: list[str] = []

    for account in accounts:
        password_hash = pwd_context.hash(account.contrasena)
        cursor.execute(
            "SELECT id_usuario FROM usuarios WHERE correo = :correo",
            {"correo": account.correo},
        )
        existing_user = cursor.fetchone()
        user_id = existing_user[0] if existing_user else account.id_usuario

        if existing_user:
            cursor.execute(
                "UPDATE usuarios SET nombre = :nombre, telefono = :telefono, tipo_usuario = 'Vendedor', password_hash = :password_hash "
                "WHERE correo = :correo",
                {
                    "nombre": account.nombre,
                    "telefono": account.telefono,
                    "password_hash": password_hash,
                    "correo": account.correo,
                },
            )
        else:
            cursor.execute(
                "INSERT INTO usuarios (id_usuario, nombre, telefono, correo, tipo_usuario, password_hash) "
                "VALUES (:id_usuario, :nombre, :telefono, :correo, 'Vendedor', :password_hash)",
                {
                    "id_usuario": user_id,
                    "nombre": account.nombre,
                    "telefono": account.telefono,
                    "correo": account.correo,
                    "password_hash": password_hash,
                },
            )

        vendor_ids.append(user_id)

        cursor.execute(
            "SELECT id_vendedor FROM vendedores WHERE id_vendedor = :id_vendedor",
            {"id_vendedor": user_id},
        )
        existing_vendor = cursor.fetchone()

        if existing_vendor:
            cursor.execute(
                "UPDATE vendedores SET codigo_vendedor = :codigo_vendedor, especialidad = :especialidad, objetivo_ventas = :objetivo_ventas "
                "WHERE id_vendedor = :id_vendedor",
                {
                    "codigo_vendedor": account.codigo_vendedor,
                    "especialidad": account.especialidad,
                    "objetivo_ventas": account.objetivo_ventas,
                    "id_vendedor": user_id,
                },
            )
        else:
            cursor.execute(
                "INSERT INTO vendedores (id_vendedor, codigo_vendedor, especialidad, objetivo_ventas) "
                "VALUES (:id_vendedor, :codigo_vendedor, :especialidad, :objetivo_ventas)",
                {
                    "id_vendedor": user_id,
                    "codigo_vendedor": account.codigo_vendedor,
                    "especialidad": account.especialidad,
                    "objetivo_ventas": account.objetivo_ventas,
                },
            )

        credentials_rows.append((account.nombre, account.correo, account.contrasena))

    return credentials_rows, vendor_ids


def assign_products(cursor, vendor_ids: list[str]) -> int:
    cursor.execute("DELETE FROM producto_vendedor")
    product_ids = fetch_products(cursor)
    if not product_ids or not vendor_ids:
        return 0

    for index, product_id in enumerate(product_ids):
        vendor_id = vendor_ids[index % len(vendor_ids)]
        cursor.execute(
            "INSERT INTO producto_vendedor (id_producto, id_vendedor) VALUES (:id_producto, :id_vendedor)",
            {"id_producto": product_id, "id_vendedor": vendor_id},
        )

    return len(product_ids)


def write_credentials_file(rows: list[tuple[str, str, str]]) -> None:
    with OUTPUT_TXT.open("w", encoding="utf-8") as file_handle:
        file_handle.write("nombre\tcorreo\tcontrasena\n")
        for nombre, correo, contrasena in rows:
            file_handle.write(f"{nombre}\t{correo}\t{contrasena}\n")


def main() -> None:
    accounts = make_vendor_accounts(10)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            credentials_rows, vendor_ids = upsert_vendors(cursor, accounts)
            assigned = assign_products(cursor, vendor_ids)
        connection.commit()

    write_credentials_file(credentials_rows)
    print(
        "Redistribucion completada: "
        f"10 vendedores listos, {assigned} productos repartidos y credenciales guardadas en {OUTPUT_TXT}."
    )


if __name__ == "__main__":
    main()