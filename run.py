from __future__ import annotations

import os
import sys
import subprocess
import shutil
import platform
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"


def get_venv_python() -> Path:
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> Path:
    if not VENV_DIR.exists():
        print("Creando entorno virtual en .venv...")
        venv.create(VENV_DIR, with_pip=True)
    else:
        print("Entorno virtual encontrado (.venv)")
    python_path = get_venv_python()
    if not python_path.exists():
        raise RuntimeError(f"No se encontró el intérprete de Python en {python_path}")
    return python_path


def run_check(cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    print(f"Ejecutando: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd, env=env)


def start_process(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> subprocess.Popen:
    print(f"Iniciando: {' '.join(cmd)} (cwd={cwd})")
    return subprocess.Popen(cmd, cwd=cwd, env=env)


def main():
    python = ensure_venv()

    # Actualizar pip e instalar dependencias Python
    try:
        try:
            run_check([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        except KeyboardInterrupt:
            print("Instalación de pip interrumpida por el usuario; continuo sin actualizar pip.")

        if (ROOT / "requirements.txt").exists():
            try:
                run_check([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
            except KeyboardInterrupt:
                print("Instalación de dependencias interrumpida por el usuario; continúo.")
        else:
            print("No se encontró requirements.txt, omitiendo instalación de dependencias Python.")
    except subprocess.CalledProcessError:
        print("Error instalando dependencias Python. Revisa mensajes previos.")

    # Instalar dependencias frontend si npm está disponible
    node = shutil.which("node")
    npm = shutil.which("npm")
    frontend_dir = ROOT / "Frontend"
    if node and npm and frontend_dir.exists():
        try:
            try:
                run_check([npm, "install"], cwd=frontend_dir)
            except KeyboardInterrupt:
                print("'npm install' interrumpido por el usuario; continúo.")
        except subprocess.CalledProcessError:
            print("Error en 'npm install'. Continúo igual.")
    else:
        print("Node/npm no disponible o carpeta Frontend ausente. Salta instalación frontend.")

    # Variables de entorno para procesos (heredan las actuales)
    env = os.environ.copy()

    # Iniciar backend con uvicorn usando el python del venv
    backend_proc = None
    try:
        backend_cmd = [str(python), "-m", "uvicorn", "Backend.app:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]
        backend_proc = start_process(backend_cmd, cwd=ROOT, env=env)
    except Exception as exc:
        print(f"No se pudo iniciar el backend: {exc}")

    # Iniciar frontend con npm (dev)
    frontend_proc = None
    if npm and frontend_dir.exists():
        try:
            frontend_proc = start_process([npm, "run", "dev"], cwd=frontend_dir, env=env)
        except Exception as exc:
            print(f"No se pudo iniciar el frontend: {exc}")

    print("Backend: http://127.0.0.1:8000")
    print("Frontend: http://localhost:5173 (si npm se inició correctamente)")

    # Esperar procesos
    try:
        while True:
            time.sleep(1)
            if backend_proc and backend_proc.poll() is not None:
                print("El backend ha terminado.")
                break
            if frontend_proc and frontend_proc.poll() is not None:
                print("El frontend ha terminado.")
                break
    except KeyboardInterrupt:
        print("Deteniendo procesos...")
        if backend_proc:
            backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()


if __name__ == "__main__":
    main()
