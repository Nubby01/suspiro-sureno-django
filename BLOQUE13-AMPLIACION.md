# Bloque 13 — ampliación visual y funcional

## Alcance y etapas

Proyecto B, Django 5.1.15. Se auditó la implementación existente antes de editar. Se conservaron la navegación corregida, Trabajo asignado, los permisos por rol y los cálculos comerciales.

1. Interfaz y cuentas: colores semánticos suaves, formularios horizontales, ayudas de campo reutilizables, controles accesibles para mostrar/ocultar contraseñas y un único punto de notificaciones. Las acciones comerciales y botones de inicio mantienen su diseño.
2. Portada y cotización: fotografía real existente en Nuestra esencia, footer adaptable con los contactos públicos confirmados por el usuario, acceso permanente a Ver cotización y contador persistente en sesión. Cantidades de cajas y presentaciones diferenciadas; sin multiplicar ni alterar precios.
3. Inventario: umbral crítico opcional, alertas con nombre/cantidad/estado y ficha de insumo con historial de entradas y compras identificadas, saldos y caducidades conocidas. Trazabilidad FEFO autorizada por el usuario.
4. Demostración: filtro reversible de ejemplos en las listas de cotizaciones, pedidos, producción, inventario, catálogo interno, clientes y personal. Los indicadores excluyen los ejemplos. No se borra, desactiva ni renombra ningún registro.

## Stock: reglas explícitas

- Agotado: existencia cero.
- Crítico: existencia positiva e igual o menor que stock_critico, cuando ese umbral está configurado.
- Bajo: existencia positiva igual o menor que el mínimo, sin caer en crítico.
- Normal: por encima del mínimo.
- Inactivo: estado independiente para insumos desactivados.

Stock crítico es un umbral absoluto en la unidad del insumo, opcional, no negativo y no superior al mínimo. Se añadió vacío en los insumos anteriores; no se inventaron porcentajes ni valores de negocio. Las alertas del panel son informativas y no se repiten como notificaciones en cada navegación.

## Compras, entradas y lotes

Cada entrada nueva genera un abastecimiento trazable con cantidad inicial, saldo y unidad. Es una compra solamente si administración lo marca. Fecha de compra, importe total pagado, proveedor/origen, caducidad, referencia de lote y observaciones son opcionales y se registran únicamente cuando se conocen. El ingreso y responsable proceden del movimiento real.
La ficha conserva las entradas anteriores como entradas sin datos de compra/lote. No se infieren proveedores, fechas, precios o compras a partir de un motivo de ajuste.
La última compra registrada se identifica entre los abastecimientos marcados como compra. La caducidad más próxima se consulta solo entre lotes con saldo positivo y fecha conocida; se indica si está vencida.

FEFO: los descuentos existentes de producción y los ajustes negativos reducen primero el lote de caducidad conocida más próxima; los empates usan fecha de ingreso. Después se usan lotes sin fecha y, finalmente, existencia sin lote registrado. Cada salida de lote queda vinculada al movimiento. Los ajustes positivos aumentan el saldo sin lote. Los saldos y el total se actualizan en la misma transacción, sin doble aplicación en reintentos.
El consumo total, sus validaciones de recetas/stock, el momento de descuento y las reglas provisionales siguen siendo los anteriores. Las caducidades son informativas; no se inventó un bloqueo de producción ni devolución automática.

## Migración necesaria y conservación

`inventario.0002_abastecimientos_stock_critico` agrega el campo opcional y los modelos Abastecimiento y SalidaLote con restricciones de integridad. No elimina campos ni registros y no crea lotes retroactivos.
Se creó un respaldo privado consistente de SQLite. La migración se aplicó primero en una copia y se compararon todos los campos anteriores. Django solo añadió los tipos/permisos técnicos de los modelos nuevos; no se asignaron a cuentas. Tras esa comprobación se aplicó a la base local de Proyecto B.
La base no fue reemplazada. Se conservaron el catálogo, todos los movimientos anteriores y los roles; las comprobaciones de integridad y relaciones SQLite dieron OK. No se ejecutaron cargas de demostración ni flush sobre la base real. Las pruebas y previews usan bases aisladas.
En otra instalación: respaldar su base, copiar el código y ejecutar `python manage.py migrate`. En esta carpeta la migración ya está aplicada.

## Contactos y seguridad

El usuario confirmó expresamente que los contactos proporcionados son públicos del negocio. Están centralizados en .env local y se consumen por la configuración existente, tanto para el footer/WhatsApp como para el PDF. No se duplicaron en plantillas ni se incluyen en el paquete de código.
El control de contraseña cambia solo el tipo visible del campo, conserva su valor, usa etiqueta accesible y lo vuelve a ocultar al enviar. No registra ni muestra contraseñas en notificaciones. Los mensajes de autenticación son genéricos y los avisos de productos no repiten nombres internos en páginas públicas.
Las validaciones, límites de cantidad, precios del servidor, permisos y CSRF se conservan.

## Registros de demostración identificados

Se usan únicamente los prefijos explícitos DEMO · y Ejemplo de prueba, o los tres identificadores de cuenta que ya utilizaba el comando de demostración. No se deduce que una persona o un producto sea ficticio por su nombre.

| Tipo | Cantidad | IDs internos |
|---|---:|---|
| Insumos | 10 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 |
| Productos | 0 | Ninguno |
| Cotizaciones | 5 | 2, 3, 4, 5, 6 |
| Pedidos | 5 | 1, 2, 3, 4, 5 |
| Cuentas | 3 | 3, 4, 5 |

Se conservan sus relaciones. Activar Mostrar registros de demostración y Aplicar para revisarlos. No se implementó eliminación definitiva: la opción segura elegida es ocultarlos reversiblemente.

## Uso y límites documentados

Configurar umbrales críticos reales para los insumos que los requieran. Las compras y caducidades antiguas no pueden reconstruirse sin información verificada; sus espacios permanecen vacíos. Los nuevos abastecimientos quedan listos para registrarse.
Las pantallas se revisan en Chromium en escritorio, tabletas y móviles; no se afirma validación en Safari/iOS. El contador usa la sesión y las redirecciones existentes, sin añadir AJAX ni cambiar la persistencia. Las muestras visuales contienen clientes y compras ficticios, no datos reales.

## Archivos modificados y nuevos

- `BLOQUE13.md`
- `README.md`
- `apps/core/context_processors.py`
- `apps/core/templatetags/__init__.py`
- `apps/core/templatetags/interfaz.py`
- `apps/core/tests_ampliacion.py`
- `apps/cotizaciones/views.py`
- `apps/cuentas/views.py`
- `apps/inventario/admin.py`
- `apps/inventario/formularios.py`
- `apps/inventario/migrations/0002_abastecimientos_stock_critico.py`
- `apps/inventario/models.py`
- `apps/inventario/servicios.py`
- `apps/inventario/tests_abastecimiento.py`
- `apps/inventario/urls.py`
- `apps/inventario/views.py`
- `apps/panel/catalogo_vistas.py`
- `apps/panel/demostracion.py`
- `apps/panel/listado.py`
- `apps/panel/navegacion.py`
- `apps/panel/resumen.py`
- `apps/panel/tests_demo.py`
- `apps/panel/views.py`
- `apps/pedidos/views.py`
- `static/css/controles.css`
- `static/css/panel.css`
- `static/js/interfaz.js`
- `static/js/nav.js`
- `templates/base.html`
- `templates/catalogo/_cotizar.html`
- `templates/catalogo/detalle.html`
- `templates/catalogo/indice.html`
- `templates/core/_cabecera.html`
- `templates/core/_marca.html`
- `templates/core/_marco.html`
- `templates/core/_tarjeta_muestra.html`
- `templates/core/_volver_arriba.html`
- `templates/core/inicio.html`
- `templates/cotizaciones/consulta.html`
- `templates/cotizaciones/gestion_detalle.html`
- `templates/cotizaciones/gestion_lista.html`
- `templates/cotizaciones/solicitud.html`
- `templates/cuentas/403.html`
- `templates/cuentas/_pagina.html`
- `templates/cuentas/cambiar_clave.html`
- `templates/cuentas/ingresar.html`
- `templates/cuentas/mi_cuenta.html`
- `templates/cuentas/registro.html`
- `templates/inventario/ficha.html`
- `templates/inventario/insumo_formulario.html`
- `templates/inventario/insumos.html`
- `templates/inventario/movimiento_formulario.html`
- `templates/inventario/produccion_detalle.html`
- `templates/inventario/produccion_lista.html`
- `templates/inventario/receta_formulario.html`
- `templates/inventario/recetas.html`
- `templates/panel/catalogo.html`
- `templates/panel/catalogo_formulario.html`
- `templates/panel/catalogo_galeria.html`
- `templates/panel/catalogo_variantes.html`
- `templates/panel/clientes.html`
- `templates/panel/indice.html`
- `templates/panel/personal.html`
- `templates/pedidos/gestion_detalle.html`
- `BLOQUE13-AMPLIACION.md`

## Validación definitiva y entrega

- `python manage.py check`: sin incidencias.
- `python manage.py test --noinput`: 179 tests aprobados en 276.966 segundos, con configuración normal de contraseñas y base de pruebas aislada.
- `python manage.py makemigrations --check --dry-run`: No changes detected.
- Diez pruebas nuevas de lotes, FEFO, reintentos, rollback, umbrales, historial, permisos, contador, DEMO y autenticación; también repetidas tras los ajustes finales.
- Chromium: 15 pantallas en cinco anchos (320, 390, 768, 1024 y 1440 px), sin desbordamientos horizontales ni errores JavaScript. Formatos horizontales/móviles inspeccionados visualmente; mostrar/ocultar contraseña conserva el valor y se reoculta al enviar; menús y contactos verificados.
- PDF de prueba con contactos públicos configurados: revisado visualmente, con cliente ficticio. Se conserva el generador y sus cálculos previamente verificados.
- Catálogo, movimientos anteriores y roles conservados; integridad y relaciones SQLite correctas.
- Proyecto A no se modificó. No se eliminaron registros de demostración.

El ZIP entregado contiene solo archivos de código y documentación modificados o nuevos, incluida la migración. Excluye db.sqlite3, .env, respaldos privados, entornos, cachés y logs. La aplicación activa ya tiene los cambios: no hace falta extraer el paquete allí. Para otra copia, conservar su base/configuración y ejecutar migrate.

La configuración de umbrales y el registro de futuras compras requieren valores reales del negocio. No se reconstruyeron fechas ni compras antiguas por suposición. La eliminación definitiva de DEMO queda fuera: se optó por ocultarlos de forma reversible.
