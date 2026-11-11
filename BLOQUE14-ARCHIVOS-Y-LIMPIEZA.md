# Proyecto B: archivos de ejecución, mantenimiento y limpieza

Revisión del 11 de noviembre de 2026. No se eliminó ningún archivo.

## Puedes retirar artefactos regenerables

| Ruta o patrón | Trabajo que realiza | Recomendación |
|---|---|---|
| `**/__pycache__/`, `*.pyc`, `*.pyo` | Caché de Python | Se pueden eliminar con el servidor detenido; se regeneran. |
| `staticfiles/` | Copia creada por collectstatic, incluida la del admin | Se puede eliminar localmente y volver a generar; no borrar `static/`. Vercel la genera al construir. |
| `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/` si aparecen | Cachés e informes de herramientas | Prescindibles para servir la web. |
| Logs y temporales (`*.log`, `*.tmp`, `*.temp`) | Diagnóstico temporal | Revisar si contienen información útil; no subirlos. |
| ZIP de entregas anteriores | Copias de distribución | No participan en la aplicación; conservar fuera del repositorio solo si sirven de respaldo. |

## No se ejecutan al navegar, pero conviene conservarlos

- **23 archivos `test*.py` (229.531 bytes, aproximadamente 224 KiB):** pruebas de permisos, precios, inventario, PDF y navegación. No se ejecutan al visitar la web. Conservar en GitHub; `vercel.json` los excluye del paquete de la función. Borrarlos ahorra muy poco y elimina la verificación de futuros cambios.
- **Documentación `.md`:** instrucciones e informes; no interviene en las respuestas de Django. Puede archivarse documentación antigua tras consolidarla, pero conservar README y Bloque 14 para operar la aplicación. Se excluye del paquete de la función.
- **`scripts/`:** utilidades manuales para comprobar producción, respaldar y ensayar el catálogo; no se ejecutan automáticamente. Conservar para mantenimiento.
- **Comandos manuales de `management/commands/`:** `crear_cuentas_demostracion.py` y `cargar_demo_negocio.py` solo sirven para demostraciones locales y no arrancan con el servidor. Los otros cinco comandos importan catálogo/fotos, revisan precios o cargan configuraciones comerciales. Conservar hasta revisar sus dependencias y decidir si se necesitarán para reconstruir una base nueva. No ejecutar cargas durante el despliegue.
- **`config/asgi.py`:** entrada alternativa no seleccionada por la configuración WSGI actual. Es opcional en esta instalación, pero no hace falta borrarla y pesa muy poco.

## Excluir del repositorio y del despliegue, sin borrarlos del equipo

- `.env` y variantes: configuración privada. Conservar `.env.example`, que no contiene credenciales reales.
- `db.sqlite3` y archivos auxiliares: base local con catálogo, cuentas e historial. **No borrar.** Neon no la sustituye automáticamente.
- `respaldos_locales/`, `backups/`, `private_data/`, exportaciones SQL y fixtures privadas: copias necesarias para recuperar datos. Mantener protegidas fuera de Git.
- `.venv/`: dependencias instaladas para este equipo; no se sube. Se puede reconstruir desde requirements, pero la instalación local depende de ella mientras se usa.
- `.git/`, `.vercel/`, configuraciones del editor: no son recursos públicos de la web.

## Mantener para que funcione y pueda reconstruirse

`manage.py`, `config/settings.py`, `config/base_datos.py`, `config/entorno.py`, `config/urls.py`, `config/wsgi.py`, los módulos de aplicaciones, plantillas, CSS, JavaScript, logo, fotografías, archivos `__init__.py`, requirements y **todas las migraciones**. Las migraciones no atienden cada visita, pero construyen el esquema de Neon y las siguientes actualizaciones.

No declarar fotografías o módulos como sobrantes solo porque su nombre no aparece en una plantilla: el catálogo usa referencias dinámicas y los comandos de mantenimiento reutilizan servicios. No se encontró un conjunto de fotos que pueda borrarse con seguridad.

La limpieza propuesta separa artefactos regenerables de herramientas útiles; no elimina funciones ni datos. No se inicializó un repositorio ni se hizo push.
