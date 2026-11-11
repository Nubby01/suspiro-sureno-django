# Verificación de entrega

- Suite completa: `python manage.py test --noinput`: 166 tests, OK, 262.941 segundos.
- Configuración normal de contraseñas (PBKDF2); base de pruebas aislada, destruida al terminar.
- `python manage.py check`: System check identified no issues (0 silenced).
- `python manage.py makemigrations --check --dry-run`: No changes detected.
- Migraciones ejecutadas desde cero en SQLite en memoria: OK.
- Pruebas nuevas: filtrado por asignación, denegación GET/POST ajenos, prohibición de asignar como ayudante, validación de responsables, retirada de asignación, roles, CSRF, enlaces de navegación vacía y botón Gestionar.
- Recorrido integral adaptado para asignar desde administración antes de avanzar producción; controles existentes de stock y consumo único aprobados.
- Revisión de entrega: selección explícita de tipos de archivo; sin db.sqlite3, .env, .git, .venv, __pycache__, .pyc ni logs. Contactos personales identificados retirados de código y pruebas.
- No se realizó comprobación visual interactiva en navegador ni despliegue externo. Los tests verifican respuestas Django, HTML y enlaces; la base de negocio no se incluyó ni modificó.
