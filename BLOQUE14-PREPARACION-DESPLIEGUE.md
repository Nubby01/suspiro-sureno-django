# Bloque 14 — Preparación de Proyecto B para Vercel, Neon y GitHub

Fecha de revisión: 11 de noviembre de 2026. Preparación local; no se desplegó ni se crearon recursos remotos. Se conserva Django 5.1.15 por alcance del proyecto. La base local no se migra ni se sustituye.

## Auditoría previa a las modificaciones

- `manage.py` en la raíz; `config.settings` y entrada `config.wsgi.application` convencionales. Sin configuración antigua de Vercel.
- SQLite local y función de selección PostgreSQL ya existente; Psycopg y su paquete binario ya estaban en requirements. Faltaban exigencia de PostgreSQL/TLS en producción y dominios configurables.
- Autenticación web con sesiones y roles; API con JWT. Se mantienen CSRF, permisos y cookies HttpOnly. El secreto de firma debe ser estable entre instancias y distinto del de desarrollo.
- 73 recursos estáticos propios, 81.089.658 bytes aproximadamente (77,3 MiB): CSS, JavaScript, imágenes y logo. El catálogo mantiene referencias a estáticos; no se encontraron FileField/ImageField ni cargas dinámicas de usuarios.
- PDF con ReportLab y BytesIO; lee el logo de `static/imagenes/logo.png`, sin archivos PDF persistentes. Esa imagen debe permanecer dentro del paquete Python.
- Datos iniciales verificados: 7 categorías, 27 productos, 35 variantes y 7 elementos de galería. SQLite íntegro. No se imprimieron cuentas, contraseñas ni tokens privados.
- Existen comandos de demostración/importación manuales. No se ejecutan al arrancar Django y no se añaden a la construcción de Vercel.
- No se encontraron trabajos que necesiten un proceso permanente. El caché local usado para limitar intentos de la API no se comparte entre instancias; validar protección distribuida antes de exponer esa API al tráfico real.

## Archivos preparados

- `config/settings.py`: entorno, producción estricta, dominios, CSRF, HTTPS, cookies, sesiones en BD y STATIC_ROOT.
- `config/entorno.py`: lectura y validación explícita de variables.
- `config/base_datos.py`: PostgreSQL/TLS, timeout, channel_binding y cursores compatibles con pool transaccional; SQLite solo en desarrollo.
- `.env.example`: variables de ejemplo sin credenciales reales. El `.env` local existente permanece intacto.
- `.gitignore` y `.vercelignore`: exclusiones de secretos, SQLite, respaldos, entornos, cachés, exportaciones y artefactos.
- `.python-version`: Python 3.12, para coincidir con el entorno local y un runtime soportado.
- `vercel.json`: configuración mínima de la función WSGI: máximo de 30 segundos y exclusión de pruebas/documentación/datos locales del paquete de ejecución. Sin builders antiguos, rutas de captura ni carpeta `/api`.
- `scripts/verificar_produccion.py`: check --deploy con entorno ficticio, conexiones de BD prohibidas, prueba de WSGI/HTTPS/CSRF/hosts/errores y PDF sintético.
- `scripts/ensayar_catalogo.py`: copia consistente de solo lectura, exportación UTF-8, importación y comparación en SQLite temporal; no traslada cuentas ni historial personal.
- `scripts/respaldar_sqlite.py`: respaldo consistente, sin sobrescribir y con integrity_check.
- `apps/core/tests_despliegue.py`: validación de configuración y URL sin conexiones.
- `apps/panel/alertas.py` y `apps/panel/test_notificaciones.py`: corrección de una regresión detectada por la suite; la campana no expone registros marcados inequívocamente como demostración.
- `BLOQUE14-ARCHIVOS-Y-LIMPIEZA.md`: inventario de archivos prescindibles para ejecución y recomendaciones.
- `README.md`: acceso a estas instrucciones.

No se cambian modelos, migraciones, reglas de negocio, permisos, productos, precios, fotos ni cantidades de inventario. Requirements no necesitó paquetes nuevos.

## Vercel: configuración posterior, todavía sin ejecutar

La detección actual usa manage.py y WSGI_APPLICATION. STATIC_ROOT permite a Vercel ejecutar collectstatic y servir estáticos desde su CDN. No hace falta añadir WhiteNoise ni ejecutar migraciones durante la construcción. [Django en Vercel](https://vercel.com/docs/frameworks/full-stack/django).

Crear más adelante un proyecto exclusivo y seleccionar como raíz la carpeta que contiene manage.py. Mantener el preset Django y el comando de construcción predeterminado. No conectar todavía el repositorio a Vercel: esa conexión puede iniciar el despliegue automáticamente.

El JSON limita cada petición a 30 s; el plan determina memoria y límites generales. La documentación consultada indica 2 GB por defecto y hasta 500 MB descomprimidos para Python. Medir el paquete final y las peticiones en Preview; el tamaño de las fotos no equivale al tamaño de la función con dependencias. [Límites oficiales](https://vercel.com/docs/functions/limitations).

Conservar las fotos originales en `static/` tanto para CDN como para las lecturas locales del PDF. No excluir `static/**` del paquete Python sin cambiar primero la lectura del logo. Para futuras subidas de usuarios, incorporar almacenamiento externo persistente; ni SQLite, ni sesiones en archivos, ni media local son persistencia adecuada en este entorno.

## Variables necesarias

| Variable | Desarrollo | Producción |
|---|---|---|
| `DJANGO_DEBUG` | 1 por defecto fuera de Vercel | 0; se rechaza 1 en Vercel |
| `DJANGO_SECRET_KEY` | Alternativa solo local | Obligatoria, aleatoria, al menos 50 caracteres; generar por un canal privado |
| `DJANGO_ALLOWED_HOSTS` | 127.0.0.1,localhost | Hosts exactos separados por coma, sin protocolo, rutas ni comodines |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Opcional | Orígenes HTTPS exactos separados por coma, sin barra final ni rutas |
| `DATABASE_URL` | Ausente para SQLite | URL exclusiva de Proyecto B, PostgreSQL con TLS |
| `VERCEL` | Ausente | La establece Vercel; no configurarla en el .env local |
| `DJANGO_LOAD_ENV` | 1 permite leer .env | Vercel no lee .env; 0 en verificaciones aisladas |
| `DJANGO_TRUST_PROXY` | Ausente | Solo fuera de Vercel y detrás de un proxy controlado |
| `NEGOCIO_WHATSAPP_VISIBLE`, `NEGOCIO_WHATSAPP_NUMERO`, `NEGOCIO_CORREO`, `NEGOCIO_INSTAGRAM`, `NEGOCIO_FACEBOOK` | Contactos autorizados ya guardados localmente | Configurarlos en el entorno para conservar footer/PDF; no guardar secretos ni datos personales de clientes |

No se autoriza globalmente `*.vercel.app`. Añadir expresamente el host de Preview que vaya a probarse y usar una base de ensayo separada. No compartir la base de producción con vistas previas.

Las cookies Secure, HttpOnly y SameSite=Lax se mantienen; sesiones en PostgreSQL compartidas entre instancias. El proxy HTTPS se confía automáticamente en Vercel. HSTS se configura a un año con subdominios/preload; usar un dominio dedicado con HTTPS completo y revisar el alcance antes de publicar bajo un dominio padre que sirva otras aplicaciones. No se hace una solicitud de inclusión en listas preload.

## Neon y migración: procedimiento futuro

La URL de ejecución debe ser la conexión agrupada de Neon; la conexión directa se usará para migraciones y respaldos. El parser conserva sslmode y channel_binding; CONN_MAX_AGE=0 y DISABLE_SERVER_SIDE_CURSORS=True evitan mantener estado de sesión entre transacciones del pool. [Conexión Django](https://neon.com/docs/guides/django), [pool de Neon](https://neon.com/docs/connect/connection-pooling).

No se crearon bases, cuentas ni conexiones remotas. No se ejecutó migrate contra Neon. No hay PostgreSQL local disponible en este equipo; el ensayo SQLite no acredita compatibilidad completa del importador, restricciones y concurrencia de PostgreSQL.

### Respaldo y clasificación

1. Coordinar una ventana sin escrituras para la exportación definitiva. Hacer respaldo con la API de SQLite, no copiar el archivo mientras recibe escrituras sin coordinar WAL.
2. Desde la raíz, ejemplo para un destino nuevo y privado:

```powershell
.\.venv\Scripts\python.exe scripts/respaldar_sqlite.py --origen db.sqlite3 --destino respaldos_locales/antes_neon.sqlite3
```

3. Conservar también fuentes, versión de dependencias, fotos y hashes en almacenamiento privado. No subir la base ni fixtures a GitHub o Vercel.
4. Revisar una copia aislada y construir un listado aprobado por modelo y PK: registros reales, demostración y dudosos. **No clasificar solo por el nombre.** Los diez insumos procedentes de demostración ya no llevan DEMO por petición del usuario; ese origen no convierte sus cantidades en existencias reales confirmadas.
5. Marcadores conocidos: usuarios demo-administradora/demo-ayudante/demo-clienta; nombres u observaciones DEMO o Ejemplo de prueba; recetas con alcance `ejemplo:`. Propagar la clasificación por relaciones y revisar los casos ambiguos. No exportar automáticamente personas de prueba, contraseñas de demostración ni datos personales sin revisión.
6. Antes de trasladar cuentas reales, aprobar usuarios, correos, teléfonos, roles, flags staff/superuser, grupos y permisos. Preservar hashes de contraseña solo para las cuentas autorizadas; nunca publicarlos. No trasladar sesiones activas ni logs del admin.

### Relaciones que deben viajar juntas

Categorías → productos → variantes/galerías (incluido producto_origen). Usuarios aprobados → cotizaciones y líneas → pedidos, líneas y eventos/asignaciones. Inventario: insumos y recetas/ingredientes → consumos/movimientos → abastecimientos y salidas por lote. Las relaciones son cruzadas: no cargar cada grupo como si fuera independiente. Conservar PKs y referencias de las filas elegidas, precios, snapshots comerciales y decimales exactos; no convertir importes a float ni inventar lotes antiguos.

Una relación hacia un registro excluido requiere decisión explícita: incluirlo si es real o excluir el conjunto de prueba coherente. No dejar pedidos sin su cotización ni movimientos sin su origen; no reasignar responsables ni anular claves a ciegas.

### Ensayo local disponible ahora

```powershell
.\.venv\Scripts\python.exe scripts/ensayar_catalogo.py --origen db.sqlite3
```

El script abre la fuente de solo lectura, respalda a un temporal, exporta únicamente catalogo con IDs, importa a otra SQLite migrada y compara todos sus datos y claves foráneas. Verifica referencias de fotos. La fixture se escribe explícitamente en UTF-8 para evitar errores de acentos en Windows. Los temporales se retiran al terminar. No es un importador automático para producción.

### Ensayo PostgreSQL obligatorio antes de la importación definitiva

1. Con autorización posterior, crear PostgreSQL aislado o una rama de ensayo Neon exclusiva; nunca usar Proyecto A. Trabajar con una copia revisada y, para ensayar cuentas/historial, datos sintéticos o anonimizados.
2. Instalar requirements en un entorno separado. Configurar variables de producción y URL **directa de la base de ensayo** mediante el entorno privado. Confirmar destino sin imprimir la contraseña.
3. Comprobar el plan y migrar únicamente esa base vacía. Estos comandos se documentan, **no se ejecutaron en Neon**:

```powershell
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate --noinput
```

4. Preparar la fixture desde la copia revisada; incluir explícitamente modelos aprobados. Ejemplo SOLO sobre esa copia y después de aprobar su contenido:

```powershell
python -X utf8 manage.py dumpdata catalogo auth.group cuentas.usuario cotizaciones pedidos inventario --natural-foreign --output private_data/datos_aprobados.json
```

No usar `--natural-primary`: se necesitan IDs estables. Excluir contenttypes, auth.permission, sessions y admin.logentry del traslado; migrate genera contenttypes/permisos nuevos y las claves naturales permiten resolverlos. Revisar las M2M de usuarios y grupos. La orden anterior **exporta todos los registros de esas aplicaciones en la copia revisada**: no ejecutarla sobre la base original como sustituto del filtro aprobado.

5. Comprobar que el destino de ensayo no contenga registros comerciales. Importar con loaddata dentro de su transacción, sin `--ignorenonexistent`. Django valida restricciones y restablece secuencias al cargar fixtures; comprobar después que crear un registro nuevo no choque con los PK importados.

```powershell
python manage.py loaddata private_data/datos_aprobados.json
```

6. Comparar conteos por modelo, conjuntos de PK, relaciones, precios, totales y sumas de cantidades. Verificar restricciones, unicidad de correo/nombres sin distinguir mayúsculas, 27 productos si todos siguen aprobados, fotos, galerías, roles y accesos por URL directa. Comprobar FEFO, no duplicación del consumo y transacciones concurrentes en PostgreSQL con datos ficticios.
7. Ensayar login, cotización/PDF, creación/confirmación/pedido, producción y abastecimiento. Conservar reporte privado sin tokens. Si falla, conservar el origen intacto y no continuar a producción; usar un destino nuevo para el siguiente ensayo, sin hacer flush sobre datos reales.
8. Solo después del ensayo aprobado, repetir el procedimiento en Neon de producción vacío con respaldo y ventana coordinada. Los enlaces privados de cotización requieren una decisión de conservación/rotación en esa etapa; no exponer tokens durante la revisión.
9. Cambiar Vercel a la URL agrupada y verificar Preview antes de habilitar el dominio final. Las migraciones se ejecutan manualmente una vez desde entorno de mantenimiento, nunca desde WSGI ni durante cada petición/construcción.

## GitHub: preparación, sin push ni repositorio remoto creado

Consultar `BLOQUE14-ARCHIVOS-Y-LIMPIEZA.md`. Mantener pruebas en el repositorio y excluirlas solo del paquete de ejecución. No borrar migraciones o fotos.

Cuando se autorice crear el repositorio independiente, comprobar que la carpeta no pertenezca a otro repositorio antes de inicializar. Crear un repositorio privado exclusivo de B; no usar el remoto de A. Revisar archivos concretos antes de añadirlos. Antes de cualquier commit/push:

```powershell
git status --short
git check-ignore .env db.sqlite3 .venv/ respaldos_locales/ private_data/ staticfiles/
```

Usar rutas existentes. Revisar `git diff --cached --name-only` y el contenido preparado, no solo .gitignore. Una regla ignore no elimina un secreto ya versionado: si lo hubiera, detener la publicación y revisar su historial y rotación. No se guardó ninguna credencial real en los archivos nuevos.

## Validación ejecutada

- `python manage.py check`: sin incidencias.
- `python scripts/verificar_produccion.py`: ejecuta check --deploy con fail-level WARNING en configuración de producción ficticia; sin advertencias, sin conexiones de BD. WSGI, redirección HTTPS, cookies, CSRF, host ajeno rechazado y errores 404/500 verificados.
- PDF sintético de 100 líneas: 0,353 s, 507.228 bytes en memoria en Windows local. No es una medición en Vercel ni con latencia Neon.
- `python manage.py makemigrations --check --dry-run`: sin cambios detectados.
- `python manage.py collectstatic --noinput`: 227 archivos recolectados; los 73 originales propios coinciden byte a byte con su copia recolectada. No se modificaron originales.
- `python -m pip check`: sin dependencias rotas.
- Ensayo de catálogo: 7 categorías, 27 productos, 35 variantes y 7 elementos de galería, idénticos tras la restauración aislada.
- Suite completa: `python manage.py test --noinput --parallel 4`, 194 pruebas aprobadas en 98,931 s. Incluye administradora, ayudante, cliente, catálogo, PDF e inventario. La primera ejecución completa detectó la regresión de notificaciones DEMO, corregida antes de repetir la suite.
- Comparación de datos: las 26 tablas locales coinciden con las huellas iniciales; 27 productos conservados e integrity_check correcto.
- Reglas .gitignore verificadas con Git en un repositorio temporal separado; conserva fuentes/fotos/tests y excluye secretos, bases, exportaciones y cachés. No se inicializó Git en Proyecto B.
- Utilidad de respaldo probada con base sintética: conserva contenido, no altera la fuente y rechaza sobrescribir un destino existente.

## Pendientes antes de publicar

1. Django 5.1 terminó soporte extendido el 3 de diciembre de 2025. Mantener 5.1.15 cumple el alcance de este bloque, pero **no se recomienda publicarlo así**: actualizar y probar una rama soportada (por ejemplo 5.2 LTS) en un trabajo separado. [Soporte oficial](https://www.djangoproject.com/download/).
2. Crear recursos exclusivos, revisar planes/dominios y configurar secretos reales cuando se autorice. No se verificó un build remoto de Vercel ni una conexión real a Neon.
3. Completar ensayo PostgreSQL, revisión de datos reales/de prueba, cuentas y stock físico. No asumir que el éxito en SQLite acredita los bloqueos/concurrencia de PostgreSQL.
4. Validar límites y protección compartida contra intentos de acceso de la API, monitoreo sin datos personales, respaldo y recuperación en producción. Elegir almacenamiento externo si se agregan subidas de archivos.
5. Ejecutar las verificaciones finales con el dominio HTTPS y el entorno real en Preview, sin datos privados de producción.
