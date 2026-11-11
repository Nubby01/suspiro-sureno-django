# Suspiro Sureño 2.0 — Proyecto B

Copia independiente. No modifica Proyecto A ni conecta servicios externos.

## Inicio local en Windows

Extraer en una carpeta nueva y abrirla en VS Code. En su terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001
```

Abrir http://127.0.0.1:8001/ . No se incluye base de datos ni cuentas reales.
Para el catálogo inicial: `python manage.py importar_catalogo_fotografias` (consultar `--help` y revisar sus resultados antes de cargar precios). No se inventan recetas ni precios.

## Roles y trabajo asignado

Existen los roles clienta, ayudante y administradora; un superusuario accede a gestión.
Administración crea ayudantes en Personal. En Producción → Gestionar, selecciona una ayudante activa y guarda la asignación; Sin asignar la retira.
La ayudante ve únicamente sus pedidos pendientes en Trabajo asignado y Producción. El acceso directo a otro pedido devuelve 404. Puede registrar los avances existentes; no asignar, cancelar ni cambiar precios.
El consumo sigue ocurriendo una sola vez al iniciar preparación, con receta y stock suficientes.

## Privacidad y configuración

La entrega excluye SQLite, .env, entornos virtuales, historial Git y cachés.
Los contactos personales antes incrustados se retiraron. Completar NEGOCIO_* en .env local; los enlaces de contacto vacíos no se muestran. No publicar .env.
Si se aplica el código a otra copia con datos, respaldarla y ejecutar `manage.py migrate` para agregar responsable; los pedidos existentes quedan sin asignar.

Ver CAMBIOS.md para alcance, archivos y pendientes verificables.


## Continuación del Bloque 13

Ver `BLOQUE13.md` para la auditoría, los grupos de cambios, archivos y verificaciones.
Esta actualización incorpora `reportlab==5.1.0` para el PDF comercial. Ya está instalado en el entorno local de trabajo. En otra instalación ejecutar `python -m pip install -r requirements.txt`.
La etapa visual inicial no necesitó migraciones; la ampliación de abastecimientos descrita más abajo sí las requiere. Conserva la base restaurada existente; el paquete de cambios no contiene SQLite ni configuraciones privadas.
Después de abrir el sitio, actualizar con Ctrl+F5 para obtener los estilos nuevos.


## Ampliación funcional de Bloque 13

Ver `BLOQUE13-AMPLIACION.md` para funcionalidades, verificación y conservación de datos.
La migración `inventario.0002_abastecimientos_stock_critico` es necesaria para los nuevos umbrales y la trazabilidad. Ya está aplicada en esta carpeta. En otra instalación, respaldar SQLite y ejecutar `python manage.py migrate` antes de abrir la aplicación.
Los contactos públicos autorizados están en la configuración `.env` local. Conservar ese archivo; no se incluye en los paquetes de código.
Stock crítico: configurar un umbral absoluto opcional en cada insumo, entre cero y el mínimo. Agotado se muestra aparte. Sin configuración no se inventa un umbral crítico.
Los lotes y datos de compra se registran desde las entradas nuevas. La existencia previa y los ajustes positivos se conservan como saldo sin lote. FEFO descuenta primero las caducidades conocidas más próximas, luego los lotes sin fecha y finalmente el saldo sin lote; las fechas son informativas y no cambian las reglas de producción.
Los registros DEMO se ocultan en listas operativas; activar Mostrar registros de demostración para revisarlos. No se eliminaron.
Actualizar el navegador con Ctrl+F5.


## Ajustes finales antes del despliegue

Ver `BLOQUE13-AJUSTES-FINALES.md` para cambios y verificación. Esta etapa no añade migraciones ni cambia datos o reglas comerciales. El indicador de cotización volvió al menú principal. Centro y sabores tienen un selector progresivo; si el navegador no admite Popover, se conserva el select nativo. Los demás selectores siguen nativos con campos y focos coherentes.
Los cambios están aplicados localmente; no se desplegó. Recargar con Ctrl+F5 para obtener los recursos actualizados. La revisión en dispositivos físicos, Safari/iOS y lectores de pantalla reales no está incluida en las pruebas realizadas.


### Desplegables y contador de cotización

Todos los desplegables simples del sitio y panel utilizan el menú cálido compartido, con teclado y respaldo nativo si Popover no está disponible. Se conservan los controles múltiples y las listas de varias filas.
La insignia de Ver cotización se muestra solamente cuando hay presentaciones seleccionadas; al quitar la última desaparece. Se mantiene el enlace visible y la persistencia de sesión existente.


## Bloque 14: preparación de despliegue

Ver [BLOQUE14-PREPARACION-DESPLIEGUE.md](BLOQUE14-PREPARACION-DESPLIEGUE.md) para Vercel, Neon, variables, ensayos y pendientes de seguridad; y [BLOQUE14-ARCHIVOS-Y-LIMPIEZA.md](BLOQUE14-ARCHIVOS-Y-LIMPIEZA.md) antes de retirar archivos. La preparación no publica el proyecto ni modifica la base local.
