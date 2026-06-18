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

DIR_RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(DIR_RAIZ / ".env")

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_DSN = os.environ["DB_DSN"]
WALLET_PATH = os.environ.get("WALLET_PATH") or os.environ.get("WALLET_LOCATION")
WALLET_PASSWORD = os.environ.get("WALLET_PASSWORD", "")

if not WALLET_PATH:
    _wallet_root = DIR_RAIZ / "wallet"
    if _wallet_root.is_dir():
        for _child in sorted(_wallet_root.iterdir()):
            if _child.is_dir() and (_child / "tnsnames.ora").is_file():
                WALLET_PATH = str(_child)
                break

if not WALLET_PATH:
    raise RuntimeError("WALLET_PATH no definido en .env")

ubicacion_wallet = Path(WALLET_PATH)
if not ubicacion_wallet.is_absolute():
    ubicacion_wallet = (DIR_RAIZ / ubicacion_wallet).resolve()

contexto_contrasena = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ARCHIVO_SALIDA = DIR_RAIZ / "vendedores_demo.txt"

NOMBRES = [
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

APELLIDOS = [
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

ESPECIALIDADES = ["Bebidas", "Despensa", "Tecnologia", "Hogar", "Belleza", "Limpieza", "Farmacia", "Accesorios"]


@dataclass(frozen=True)
class CuentaVendedor:
    id_usuario: str
    nombre: str
    telefono: str
    correo: str
    contrasena: str
    codigo_vendedor: str
    especialidad: str
    objetivo_ventas: float


def obtener_conexion():
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        config_dir=str(ubicacion_wallet),
        wallet_location=str(ubicacion_wallet),
        wallet_password=WALLET_PASSWORD,
    )


def generar_cuentas_vendedores(cantidad: int = 10) -> list[CuentaVendedor]:
    aleatorio = random.Random(20260525)
    cuentas: list[CuentaVendedor] = []

    for indice in range(1, cantidad + 1):
        nombre_pila = aleatorio.choice(NOMBRES)
        apellido = aleatorio.choice(APELLIDOS)
        segundo_apellido = aleatorio.choice(APELLIDOS)
        nombre = f"{nombre_pila} {apellido} {segundo_apellido}"
        correo = f"vendedor_demo_{indice:02d}@demo.local"
        contrasena = f"Vnd-{indice:02d}-{secrets.token_hex(4)}"
        telefono = f"55{aleatorio.randint(10000000, 99999999)}"
        codigo_vendedor = f"V-{3000 + indice}"
        especialidad = aleatorio.choice(ESPECIALIDADES)
        objetivo_ventas = float(aleatorio.randint(80000, 220000))
        id_usuario = str(uuid.uuid5(uuid.NAMESPACE_URL, correo))

        cuentas.append(
            CuentaVendedor(
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

    return cuentas


def obtener_productos(cursor):
    cursor.execute("SELECT id_producto FROM productos ORDER BY nombre, id_producto")
    return [fila[0] for fila in cursor.fetchall()]


def insertar_o_actualizar_vendedores(cursor, cuentas: list[CuentaVendedor]) -> tuple[list[tuple[str, str, str]], list[str]]:
    filas_credenciales: list[tuple[str, str, str]] = []
    ids_vendedores: list[str] = []

    for cuenta in cuentas:
        hash_contrasena = contexto_contrasena.hash(cuenta.contrasena)
        cursor.execute(
            "SELECT id_usuario FROM usuarios WHERE correo = :correo",
            {"correo": cuenta.correo},
        )
        usuario_existente = cursor.fetchone()
        id_usuario = usuario_existente[0] if usuario_existente else cuenta.id_usuario

        if usuario_existente:
            cursor.execute(
                "UPDATE usuarios SET nombre = :nombre, telefono = :telefono, tipo_usuario = 'Vendedor', password_hash = :password_hash "
                "WHERE correo = :correo",
                {
                    "nombre": cuenta.nombre,
                    "telefono": cuenta.telefono,
                    "password_hash": hash_contrasena,
                    "correo": cuenta.correo,
                },
            )
        else:
            cursor.execute(
                "INSERT INTO usuarios (id_usuario, nombre, telefono, correo, tipo_usuario, password_hash) "
                "VALUES (:id_usuario, :nombre, :telefono, :correo, 'Vendedor', :password_hash)",
                {
                    "id_usuario": id_usuario,
                    "nombre": cuenta.nombre,
                    "telefono": cuenta.telefono,
                    "correo": cuenta.correo,
                    "password_hash": hash_contrasena,
                },
            )

        ids_vendedores.append(id_usuario)

        cursor.execute(
            "SELECT id_vendedor FROM vendedores WHERE id_vendedor = :id_vendedor",
            {"id_vendedor": id_usuario},
        )
        vendedor_existente = cursor.fetchone()

        if vendedor_existente:
            cursor.execute(
                "UPDATE vendedores SET codigo_vendedor = :codigo_vendedor, especialidad = :especialidad, objetivo_ventas = :objetivo_ventas "
                "WHERE id_vendedor = :id_vendedor",
                {
                    "codigo_vendedor": cuenta.codigo_vendedor,
                    "especialidad": cuenta.especialidad,
                    "objetivo_ventas": cuenta.objetivo_ventas,
                    "id_vendedor": id_usuario,
                },
            )
        else:
            cursor.execute(
                "INSERT INTO vendedores (id_vendedor, codigo_vendedor, especialidad, objetivo_ventas) "
                "VALUES (:id_vendedor, :codigo_vendedor, :especialidad, :objetivo_ventas)",
                {
                    "id_vendedor": id_usuario,
                    "codigo_vendedor": cuenta.codigo_vendedor,
                    "especialidad": cuenta.especialidad,
                    "objetivo_ventas": cuenta.objetivo_ventas,
                },
            )

        filas_credenciales.append((cuenta.nombre, cuenta.correo, cuenta.contrasena))

    return filas_credenciales, ids_vendedores


def asignar_productos(cursor, ids_vendedores: list[str]) -> int:
    cursor.execute("DELETE FROM producto_vendedor")
    ids_productos = obtener_productos(cursor)
    if not ids_productos or not ids_vendedores:
        return 0

    for indice, id_producto in enumerate(ids_productos):
        id_vendedor = ids_vendedores[indice % len(ids_vendedores)]
        cursor.execute(
            "INSERT INTO producto_vendedor (id_producto, id_vendedor) VALUES (:id_producto, :id_vendedor)",
            {"id_producto": id_producto, "id_vendedor": id_vendedor},
        )

    return len(ids_productos)


def escribir_archivo_credenciales(filas: list[tuple[str, str, str]]) -> None:
    with ARCHIVO_SALIDA.open("w", encoding="utf-8") as manejador_archivo:
        manejador_archivo.write("nombre\tcorreo\tcontrasena\n")
        for nombre, correo, contrasena in filas:
            manejador_archivo.write(f"{nombre}\t{correo}\t{contrasena}\n")


def principal() -> None:
    cuentas = generar_cuentas_vendedores(10)

    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            filas_credenciales, ids_vendedores = insertar_o_actualizar_vendedores(cursor, cuentas)
            asignados = asignar_productos(cursor, ids_vendedores)
        conexion.commit()

    escribir_archivo_credenciales(filas_credenciales)
    print(
        "Redistribucion completada: "
        f"10 vendedores listos, {asignados} productos repartidos y credenciales guardadas en {ARCHIVO_SALIDA}."
    )


if __name__ == "__main__":
    principal()