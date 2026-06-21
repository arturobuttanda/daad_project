from __future__ import annotations

import os
import sys
import subprocess
import shutil
import platform
import time
import venv
import webbrowser
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_VENV = RAIZ / ".venv"


def obtener_python_venv() -> Path:
    if platform.system() == "Windows":
        return DIR_VENV / "Scripts" / "python.exe"
    return DIR_VENV / "bin" / "python"


def asegurar_venv() -> Path:
    if not DIR_VENV.exists():
        print("Creando entorno virtual en .venv...")
        venv.create(DIR_VENV, with_pip=True)
    else:
        print("Entorno virtual encontrado (.venv)")
    ruta_python = obtener_python_venv()
    if not ruta_python.exists():
        raise RuntimeError(f"No se encontro el interprete de Python en {ruta_python}")
    return ruta_python


def ejecutar_comando(comando: list[str], cwd: Path | None = None, env: dict | None = None, silencioso: bool = False):
    if silencioso:
        subprocess.check_call(comando, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print(f"Ejecutando: {' '.join(comando)}")
        subprocess.check_call(comando, cwd=cwd, env=env)


def iniciar_proceso(comando: list[str], cwd: Path | None = None, env: dict | None = None, stdout=None, stderr=None) -> subprocess.Popen:
    return subprocess.Popen(comando, cwd=cwd, env=env, stdout=stdout, stderr=stderr)


def principal():
    python = asegurar_venv()

    # Instalar dependencias Python de forma silenciosa
    try:
        print("Verificando dependencias de Python (esto puede tomar unos segundos)...")
        try:
            ejecutar_comando([str(python), "-m", "pip", "install", "--upgrade", "pip"], silencioso=True)
        except KeyboardInterrupt:
            print("Instalacion de pip interrumpida; continuo sin actualizar.")

        if (RAIZ / "requirements.txt").exists():
            try:
                ejecutar_comando([str(python), "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")], silencioso=True)
            except KeyboardInterrupt:
                print("Instalacion de dependencias interrumpida; continuo.")
        else:
            print("No se encontro requirements.txt, omitiendo instalacion.")
    except subprocess.CalledProcessError:
        print("Nota: Hubo un detalle al verificar dependencias, pero continuaremos con la ejecucion.")

    env = os.environ.copy()
    DIR_FRONTEND = RAIZ / "Frontend"

    # Preparar archivos de log para que no ensucien la terminal
    log_out = open(RAIZ / "server_out.log", "a", encoding="utf-8")
    log_err = open(RAIZ / "server_err.log", "a", encoding="utf-8")

    # Iniciar backend con uvicorn
    proceso_backend = None
    print("Levantando backend...", end="", flush=True)
    try:
        comando_backend = [
            str(python), "-m", "uvicorn", "Backend.app:app",
            "--reload", "--host", "0.0.0.0", "--port", "8000",
        ]
        proceso_backend = iniciar_proceso(comando_backend, cwd=RAIZ, env=env, stdout=log_out, stderr=log_err)
    except Exception as exc:
        print(f"\nNo se pudo iniciar el backend: {exc}")

    # Esperar a que el backend esté listo
    backend_listo = False
    for intento in range(50):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/ping", timeout=3):
                print(" listo.")
                backend_listo = True
                break
        except Exception:
            time.sleep(1)

    if not backend_listo:
        print(" No se pudo conectar con el backend.")
        if proceso_backend:
            proceso_backend.terminate()
            proceso_backend.wait()
        return

    # Iniciar servidor estatico para el frontend HTML
    proceso_frontend = None
    if DIR_FRONTEND.exists():
        # Asegurar que la imagen de login este en el frontend
        imagen_origen = RAIZ / "ImagenLogin.png"
        imagen_destino = DIR_FRONTEND / "ImagenLogin.png"
        if imagen_origen.exists():
            try:
                shutil.copy2(imagen_origen, imagen_destino)
            except Exception:
                pass

        try:
            # Usar Python para servir los archivos estaticos del frontend
            comando_frontend = [
                str(python), "-m", "http.server", "5180",
                "--directory", str(DIR_FRONTEND),
            ]
            proceso_frontend = iniciar_proceso(comando_frontend, cwd=DIR_FRONTEND, env=env, stdout=log_out, stderr=log_err)
        except Exception as exc:
            print(f"No se pudo iniciar el servidor frontend: {exc}")
    else:
        print("Carpeta Frontend no encontrada.")

    print("\n" + "="*60)
    print("  Frontend: http://127.0.0.1:5180/iniciar-sesion.html")
    print("  Backend:  http://127.0.0.1:8000")
    print("="*60)

    try:
        webbrowser.open("http://127.0.0.1:5180/iniciar-sesion.html")
    except Exception:
        pass

    # Esperar procesos
    try:
        while True:
            time.sleep(1)
            if proceso_backend and proceso_backend.poll() is not None:
                print("El backend ha terminado.")
                break
            if proceso_frontend and proceso_frontend.poll() is not None:
                print("El servidor frontend ha terminado.")
                break
    except KeyboardInterrupt:
        print("Deteniendo procesos...")
        if proceso_backend:
            proceso_backend.terminate()
        if proceso_frontend:
            proceso_frontend.terminate()


if __name__ == "__main__":
    principal()
