Resumen de cambios:

- Traducción de strings y docstrings en `Backend/recomendacion_precio/similarity.py`.
- Renombrado y aliases en `Backend/app.py`, `Backend/conexion_base.py`, `Backend/modelo_poo.py` para exponer nombres en español.
- Wrappers añadidos en `Backend/conexion_base.py` para métodos en español que delegan en las implementaciones existentes.

Instrucciones sugeridas para crear PR:

```bash
# Crear rama de trabajo
git checkout -b feat/translate-backend-es

# Verificar cambios
git status
git add -A
git commit -m "Traducir backend a español: docstrings, aliases y wrappers"

# Subir rama
git push origin feat/translate-backend-es

# Crear PR desde la interfaz de GitHub comparando feat/translate-backend-es -> main
```

Notas:
- He dejado aliases inversos para mantener compatibilidad con código que use los nombres anteriores.
- Recomiendo ejecutar pruebas locales (uvicorn + Vite) y revisar endpoints que interactúan con la BD.
- Si quieres, abro el PR por ti (necesitaré permiso para ejecutar comandos `git` y credenciales habilitadas en este entorno).