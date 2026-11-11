> Esta es la revisión de la etapa visual inicial. La ampliación actual, incluidos contactos y foto de Nuestra esencia, está documentada en BLOQUE13-AMPLIACION.md.

# Bloque 13 — continuación en Proyecto B

## Auditoría previa

Se inspeccionaron plantillas, vistas, CSS y JavaScript de la carpeta activa. Ya funcionaban navegación de historiales vacíos, asignaciones de ayudantes, permisos y rutas de Producción. Se conservaron esas implementaciones.
Se detectaron estilos de acción superpuestos, primarios que perdían su color, estados sin diferenciar, módulo lateral sin marcar en detalles, categorías de portada sin enlaces ni fotografías reales, y un PDF de texto sin jerarquía comercial.
«Ver ficha» ya no estaba en el modal de sabores. Las frases «Hechos en el taller, con tiempo» y «Preparado para acompañar la mesa» tampoco figuraban en las plantillas actuales. Se reemplazó «Del taller» y se ajustaron textos de portada sin alterar descripciones comerciales guardadas.

## Grupo 1: botones y administración

- Hoja compartida controles.css: primarios, secundarios, contorno, advertencia y WhatsApp; hover cálido, foco visible, tamaño y alineación coherentes.
- Las acciones siguen usando sus mismos enlaces, formularios, parámetros y permisos. Cerrar modales conserva un fondo cálido al pasar el puntero.
- Tablas de cotizaciones, pedidos, inventario, producción, clientes y personal con superficies legibles, acciones claras y estados rotulados.
- Formularios de cotización agrupados por propósito; rechazo y cancelación diferenciados. Controles select con flecha y foco visibles.
- Menú lateral persistente en escritorio y módulo activo calculado en el servidor, también en los detalles. Se conserva el menú plegable en móvil.

## Grupo 2: catálogo, portada y cuentas

- Precios con mejor jerarquía y cifras alineadas; variantes con nombre/precio separados. Corregida la herencia de ancho que deformaba los radios de tortas.
- Se mantienen valores, cantidades, productos, categorías, fotos y precios existentes. Ningún archivo de imagen cambió.
- Modales con espacio para títulos y controles; clic en el fondo exterior, Escape y devolución de foco comprobados.
- «Descubre nuestras delicias» usa las categorías vendibles y fotografías disponibles del catálogo actual, con enlaces a sus secciones. No crea categorías ni productos.
- Mi cuenta tiene accesos y tarjetas independientes para datos y seguridad; ingreso y registro conservan campos, validaciones y destinos.
- Pie sin enlaces de contacto vacíos ni encabezados de contacto sin contenido.

## Grupo 3: cotización PDF

PDF A4 con logotipo existente, identidad cálida, datos de cliente y cotización, tabla de productos, cantidades, precios, importes y total calculado por los métodos actuales. Cabecera, encabezados de tabla y pie numerado en varias páginas.
Los precios pendientes conservan «Total pendiente». Solo se incluyen contactos comerciales ya configurados. No se añadieron dirección, RUT, impuestos, abonos, validez ni condiciones inventadas. El PDF no incorpora el token ni enlaces privados.
Dependencia añadida: ReportLab 5.1.0, instalada en el entorno activo y declarada en requirements.txt.

## Conservación y alcance

Se trabajó en la carpeta activa de Proyecto B. No se abrió ni modificó Proyecto A. No se ejecutaron cargas sobre la base real, flush, eliminaciones ni sustituciones de db.sqlite3.
Las cuatro tablas del catálogo tienen exactamente los mismos campos y registros que al inicio; SQLite integrity_check devuelve ok y siguen disponibles 27 productos públicos.
La huella global del archivo SQLite varió durante el uso simultáneo de la aplicación, confirmado por el usuario. No se revirtió esa actividad ni se afirma que el archivo completo permanezca idéntico byte a byte.
Los tests y previews usan bases aisladas; las cuentas, pedidos y PDFs de muestra contienen datos ficticios. El respaldo y paquete contienen únicamente código, sin SQLite, .env, historial, entornos ni cachés.
Modelos, migraciones, módulos de permisos y servicios comerciales permanecen sin cambios.

## Pendientes que requieren información real

- Contactos comerciales: en el entorno de verificación no se encontraron contactos NEGOCIO_* configurados. WhatsApp y los contactos se muestran cuando se configuren en el entorno local; no se recuperaron contactos personales de archivos antiguos.
- Fotografía de la sección Nuestra esencia: se conserva su reserva visual porque no hay una fotografía específica aprobada. Las fotografías existentes de productos se conservan.
- Reglas comerciales provisionales, recetas y precios pendientes continúan con sus validaciones actuales.
- La comprobación adaptable se realiza en Chromium; no se declara validación en Safari/iOS ni de entrega real de mensajes por WhatsApp.

## Archivos modificados o nuevos

- `README.md`
- `apps/catalogo/tests_precios.py`
- `apps/core/context_processors.py`
- `apps/core/negocio.py`
- `apps/core/tests_bloque13.py`
- `apps/core/views.py`
- `apps/cotizaciones/pdf.py`
- `apps/cotizaciones/views.py`
- `apps/panel/navegacion.py`
- `requirements.txt`
- `static/css/catalogo.css`
- `static/css/controles.css`
- `static/css/cuenta.css`
- `static/css/inicio.css`
- `static/css/panel.css`
- `static/js/catalogo.js`
- `templates/base.html`
- `templates/catalogo/_cotizar.html`
- `templates/catalogo/_producto.html`
- `templates/catalogo/detalle.html`
- `templates/catalogo/indice.html`
- `templates/core/_boton.html`
- `templates/core/_pie.html`
- `templates/core/_tarjeta_categoria.html`
- `templates/core/inicio.html`
- `templates/cotizaciones/consulta.html`
- `templates/cotizaciones/gestion_detalle.html`
- `templates/cotizaciones/gestion_lista.html`
- `templates/cotizaciones/mias.html`
- `templates/cotizaciones/solicitud.html`
- `templates/cuentas/_pagina.html`
- `templates/cuentas/cambiar_clave.html`
- `templates/cuentas/ingresar.html`
- `templates/cuentas/mi_cuenta.html`
- `templates/cuentas/registro.html`
- `templates/inventario/insumo_formulario.html`
- `templates/inventario/insumos.html`
- `templates/inventario/movimientos.html`
- `templates/inventario/produccion_detalle.html`
- `templates/inventario/produccion_lista.html`
- `templates/inventario/recetas.html`
- `templates/panel/catalogo.html`
- `templates/panel/catalogo_formulario.html`
- `templates/panel/catalogo_galeria.html`
- `templates/panel/catalogo_variantes.html`
- `templates/panel/cliente_detalle.html`
- `templates/panel/clientes.html`
- `templates/panel/indice.html`
- `templates/panel/personal.html`
- `templates/pedidos/gestion_detalle.html`
- `templates/pedidos/gestion_lista.html`
- `templates/pedidos/mios.html`
- `BLOQUE13.md`

## Validación final

- Django 5.1.15 en el entorno activo de Proyecto B.
- `python manage.py check`: sin incidencias.
- `python manage.py test --noinput`: 169 tests aprobados, 260.999 segundos, PBKDF2 normal, base de pruebas aislada.
- `python manage.py makemigrations --check --dry-run`: No changes detected. No se crearon migraciones.
- Permisos existentes y nuevas pruebas de detalle de administración, ayudante y cliente aprobados.
- GET de inicio, catálogo, ingreso y registro contra la base restaurada en modo solo lectura: 200.
- Catálogo: las cuatro tablas coinciden con las huellas iniciales; 27 productos públicos; integridad SQLite correcta.
- Chromium: 14 pantallas en 320, 390, 768, 1024 y 1440 px, sin desbordamiento horizontal. Modales, variantes, subtotales, Escape, devolución de foco y menú comprobados. Los previews usaron datos ficticios en SQLite en memoria.
- PDFs ficticios de 1 y 6 páginas: inspección visual de todas las páginas y extracción de texto para comprobar productos, totales y numeración. Token privado ausente comprobado por tests.
- Modelos, migraciones, permisos, servicios comerciales y fotografías sin cambios.

El archivo Bloque13-actualizacion.zip es una copia solo de archivos modificados y nuevos. Los cambios ya están aplicados en la carpeta activa; no es necesario extraerlo allí. No contiene db.sqlite3, .env, entornos, historial, cachés, logs ni muestras con datos reales.
Para ver los estilos actualizados en el navegador: Ctrl+F5.
