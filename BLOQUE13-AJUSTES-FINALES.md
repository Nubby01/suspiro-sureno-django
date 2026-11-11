# Ajustes finales del Bloque 13 — Proyecto B

## Cambios aplicados

- Navegación secundaria administrativa (Volver, Ver cliente/pedido y Gestionar): azul grisáceo pastel. Se mantienen azul pastel para editar, salvia para guardar/confirmar, rojo pastel para acciones destructivas y terracota para las acciones comerciales.
- Al elegir Cancelado en el formulario de un pedido, el botón indica Cancelar pedido en rojo. Al elegir otro avance recupera su presentación. No se cambian estado, nota, parámetros, validaciones ni transición comercial.
- Ver cotización vuelve al interior de la navbar, junto a sus opciones. Conserva la insignia y la lógica de contador/persistencia anterior. En móvil forma parte del menú desplegable.
- Los avisos están en el flujo de la página, fuera de los campos y acciones; no se superponen a la navegación. Controles de cerrar avisos y mostrar contraseña con objetivo táctil de 44 px.
- Selectores de Centro y sabores dentro de los modales: campo y lista cálidos, esquinas redondeadas, opciones con altura mínima de 44 px, foco y selección visibles. La lista usa la capa superior del navegador y limita su tamaño a la ventana disponible, incluso con zoom.

## Mejora progresiva del selector

Se aplica solo a los selects de opciones de producto marcados con data-selector-calido. Se conserva el select original con su nombre, opciones, valor, required y envío Django. No se crea otro campo con el mismo nombre.
El control expone combobox/listbox, etiqueta, estado expandido, opción activa, selección y errores. Las teclas de dirección, Home, End, Enter, Espacio y Tab permiten navegar/seleccionar; también se puede buscar escribiendo. Escape cierra solo la lista y conserva el valor; un segundo Escape puede cerrar el modal. La selección con puntero y tacto emulado está comprobada.
La validación enfoca el control visible cuando falta una selección. FormData sigue enviando una sola vez el valor original. El reset del formulario sincroniza el control.
Si Popover no está disponible, el select nativo permanece visible y operativo. Categorías, estados y filtros se conservan nativos, con el diseño de campo/foco común; su lista desplegada seguirá la apariencia del sistema. Los tamaños/variantes que ya usan radios conservan ese comportamiento.

## Pruebas realizadas

- Django 5.1.15: `python manage.py check`, sin incidencias.
- `python manage.py test --noinput`: 179 pruebas aprobadas, 272.550 segundos; configuración normal de contraseñas, base de pruebas aislada.
- `python manage.py makemigrations --check --dry-run`: No changes detected.
- 38 pantallas en 320, 375, 390, 430, 768, 1024 y 1440 px: 266 combinaciones únicas renderizadas en Chromium. Sin desbordamientos horizontales, imágenes sin cargar, errores de JavaScript ni texto visible menor a 12 px. Controles de formulario con objetivo táctil de al menos 44 px, contando la etiqueta asociada cuando corresponde.
- Revisión de capturas representativas de páginas públicas y administrativas, creación/edición, ficha de cliente, galería, historiales, formularios, avisos y modales.
- Teclado completo del selector en siete anchos, navegación sin cambiar valor hasta confirmar y Escape sin pérdida de valor. Los cinco selects de centro/sabores conservan exactamente sus valores y envío.
- Tacto emulado en Chromium, respaldo nativo sin Popover, nombre accesible Centro, selección con Espacio, pantalla de poca altura (720 × 450) y zoom 200 % emulado mediante el motor de Chromium. La lista permanece dentro del área visible.
- Cambio visual de Cancelar pedido sin cambiar FormData, restauración al elegir otro estado y avisos fuera de la zona de los campos.
- La suite conserva las pruebas de catálogo, cotizaciones y permisos de administradora, ayudante y cliente.

Las pantallas de revisión usaron una base en memoria con cuentas y pedidos ficticios. No se probaron teléfonos/tabletas físicos, Safari/iOS ni lectores de pantalla reales; no se afirma compatibilidad certificada con esas combinaciones. Se entrega para la última revisión visual solicitada antes de desplegar.

## Conservación y entrega

Las 19 tablas de catálogo, inventario, pedidos, cuentas y cotizaciones coinciden con sus huellas del inicio de esta etapa. SQLite pasa integridad y relaciones. Productos, precios, cuentas, movimientos y registros existentes no se modificaron.
No se cambiaron modelos, migraciones, módulos de permisos, servicios comerciales ni fotografías. No se reemplazó db.sqlite3, no se cargaron demostraciones en la base real y Proyecto A no se modificó. No se desplegó.
El ZIP contiene únicamente archivos modificados/nuevos de esta etapa. Excluye SQLite, .env, respaldos, entornos, cachés y logs. Los cambios ya están en la carpeta activa de Proyecto B; no es necesario extraer el ZIP sobre ella. Esta etapa no requiere migraciones nuevas.

## Referencias técnicas

- [W3C: patrón de combobox de selección sin edición](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/examples/combobox-select-only/).
- [WHATWG: Popover y capa superior del navegador](https://html.spec.whatwg.org/multipage/popover.html#the-popover-attribute).

## Archivos modificados o nuevos

- `README.md`
- `static/css/controles.css`
- `static/js/interfaz.js`
- `static/js/selectores.js`
- `templates/base.html`
- `templates/catalogo/_cotizar.html`
- `templates/catalogo/detalle.html`
- `templates/catalogo/indice.html`
- `templates/core/_avisos.html`
- `templates/core/_cabecera.html`
- `templates/core/inicio.html`
- `templates/cotizaciones/gestion_detalle.html`
- `templates/cotizaciones/gestion_lista.html`
- `templates/cuentas/_pagina.html`
- `templates/inventario/ficha.html`
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
- `templates/pedidos/gestion_detalle.html`
- `templates/pedidos/gestion_lista.html`
- `BLOQUE13-AJUSTES-FINALES.md`
