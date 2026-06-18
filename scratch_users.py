from Backend.conexion_base import db

def listar_usuarios():
    try:
        with db.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT correo, tipo_usuario FROM usuarios")
            usuarios = cursor.fetchall()
            for u in usuarios:
                print(f"{u[1]},{u[0]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    listar_usuarios()
