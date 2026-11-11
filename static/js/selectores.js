/* Mejora progresiva de todos los desplegables simples del sitio y del panel.
 * El select original conserva nombre, opciones, valor, validación y envío.
 */
(function () {
  'use strict';
  if (typeof HTMLElement.prototype.showPopover !== 'function') return;
  var abierto = null;
  function normalizar(texto) { return texto.toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  document.querySelectorAll('select:not([multiple])').forEach(function (select, numero) {
    if (select.multiple || select.size > 1 || select.options.length === 0) return;
    var label = select.labels[0];
    if (!label) return;
    if (!select.id) select.id = 'selector-calido-' + numero;
    if (!label.id) label.id = select.id + '-etiqueta';
    var marco = document.createElement('div'); marco.className = 'select-calido';
    select.parentNode.insertBefore(marco, select); marco.appendChild(select);
    var boton = document.createElement('button'); boton.type = 'button'; boton.className = 'select-calido__control';
    boton.id = select.id + '-control'; boton.setAttribute('role', 'combobox'); boton.setAttribute('aria-haspopup', 'listbox');
    boton.setAttribute('aria-expanded', 'false'); boton.setAttribute('aria-required', String(select.required));
    var texto = document.createElement('span'); texto.id = select.id + '-texto'; texto.className = 'select-calido__texto';
    boton.appendChild(texto); boton.setAttribute('aria-labelledby', label.id + ' ' + texto.id);
    var lista = document.createElement('div'); lista.className = 'select-calido__lista'; lista.id = select.id + '-lista';
    lista.setAttribute('role', 'listbox'); lista.setAttribute('aria-labelledby', label.id); lista.setAttribute('popover', 'manual');
    boton.setAttribute('aria-controls', lista.id);
    var error = document.createElement('p'); error.className = 'select-calido__error'; error.id = select.id + '-error'; error.hidden = true; error.setAttribute('role', 'alert');
    marco.appendChild(boton); marco.appendChild(lista); marco.appendChild(error);
    var items = []; var activo = select.selectedIndex; var estaAbierto = false; var buffer = ''; var ultimoCaracter = 0;
    Array.from(select.options).forEach(function (opcion, index) {
      var item = document.createElement('div'); item.className = 'select-calido__opcion'; item.id = lista.id + '-' + index;
      item.setAttribute('role', 'option'); item.textContent = opcion.textContent;
      item.setAttribute('aria-disabled', String(opcion.disabled)); lista.appendChild(item); items.push(item);
      item.addEventListener('pointerdown', function (e) { e.preventDefault(); });
      item.addEventListener('click', function (e) { e.preventDefault(); if (!opcion.disabled) { activar(index); cerrar(true); boton.focus(); } });
    });
    function habilitados() { return Array.from(select.options).map(function (opcion, i) { return opcion.disabled ? -1 : i; }).filter(function (i) { return i >= 0; }); }
    function limpiarError() { error.hidden = true; boton.removeAttribute('aria-invalid'); boton.removeAttribute('aria-describedby'); }
    function sincronizar() {
      texto.textContent = select.selectedOptions.length ? select.selectedOptions[0].textContent : 'Selecciona una opción';
      boton.disabled = select.disabled;
      items.forEach(function (item, index) { item.setAttribute('aria-selected', String(index === select.selectedIndex)); });
      if (select.validity.valid) limpiarError();
    }
    function activar(index) {
      if (!select.options[index] || select.options[index].disabled) return;
      activo = index;
      items.forEach(function (item, i) { item.classList.toggle('select-calido__opcion--activa', i === index); });
      boton.setAttribute('aria-activedescendant', items[index].id);
      // Scroll only the listbox, never the page or dialog.
      var item = items[index];
      if (item.offsetTop < lista.scrollTop) lista.scrollTop = item.offsetTop;
      else if (item.offsetTop + item.offsetHeight > lista.scrollTop + lista.clientHeight) lista.scrollTop = item.offsetTop + item.offsetHeight - lista.clientHeight;
    }
    function posicionar() {
      if (!estaAbierto) return;
      var rect = boton.getBoundingClientRect(); var viewport = window.visualViewport;
      var x = viewport ? viewport.offsetLeft : 0; var y = viewport ? viewport.offsetTop : 0;
      var ancho = viewport ? viewport.width : innerWidth; var alto = viewport ? viewport.height : innerHeight;
      var debajo = y + alto - rect.bottom - 12; var encima = rect.top - y - 12;
      var haciaArriba = debajo < 150 && encima > debajo;
      var espacio = haciaArriba ? encima : debajo;
      var altura = Math.max(32, Math.min(300, Math.max(espacio, 32), alto - 16));
      var anchura = Math.min(rect.width, ancho - 16);
      lista.style.width = anchura + 'px'; lista.style.maxHeight = altura + 'px';
      lista.style.left = Math.max(x + 8, Math.min(rect.left, x + ancho - anchura - 8)) + 'px';
      var top = haciaArriba ? rect.top - lista.offsetHeight - 6 : rect.bottom + 6;
      lista.style.top = Math.max(y + 8, Math.min(top, y + alto - lista.offsetHeight - 8)) + 'px';
    }
    function abrir() {
      if (select.disabled || !boton.getClientRects().length || !habilitados().length) return;
      if (abierto && abierto !== api) abierto.cerrar(false);
      if (estaAbierto) return;
      estaAbierto = true; abierto = api; boton.setAttribute('aria-expanded', 'true');
      lista.showPopover(); sincronizar(); posicionar();
      activar(select.selectedIndex >= 0 && !select.options[select.selectedIndex].disabled ? select.selectedIndex : habilitados()[0]);
    }
    function cerrar(confirmar) {
      if (!estaAbierto) return;
      if (confirmar && select.options[activo] && !select.options[activo].disabled && select.selectedIndex !== activo) {
        select.selectedIndex = activo;
        select.dispatchEvent(new Event('input', {bubbles:true})); select.dispatchEvent(new Event('change', {bubbles:true}));
      }
      if (lista.matches(':popover-open')) lista.hidePopover();
      estaAbierto = false; boton.setAttribute('aria-expanded', 'false'); boton.removeAttribute('aria-activedescendant');
      if (abierto === api) abierto = null;
      sincronizar();
    }
    var api = {cerrar:cerrar, posicionar:posicionar, marco:marco};
    boton.addEventListener('click', function () { if (estaAbierto) cerrar(false); else abrir(); });
    boton.addEventListener('keydown', function (e) {
      if (e.ctrlKey || e.metaKey) return;
      var key = e.key; var opciones = habilitados();
      if (key === 'Escape' && estaAbierto) { e.preventDefault(); e.stopPropagation(); cerrar(false); return; }
      if (key === 'Tab') { cerrar(true); return; }
      if (['ArrowDown','ArrowUp','Home','End','Enter',' '].indexOf(key) !== -1) {
        e.preventDefault(); e.stopPropagation();
        if (key === 'Enter' || key === ' ') { if (estaAbierto) cerrar(true); else abrir(); return; }
        var yaAbierto = estaAbierto; abrir();
        if (key === 'Home') activar(opciones[0]);
        else if (key === 'End') activar(opciones[opciones.length - 1]);
        else if (yaAbierto) { var i = opciones.indexOf(activo) + (key === 'ArrowDown' ? 1 : -1); activar(opciones[Math.max(0, Math.min(i, opciones.length - 1))]); }
        else if (key === 'ArrowUp') activar(opciones[0]);
        return;
      }
      if (key.length === 1 && !e.altKey) {
        e.preventDefault(); var ahora = Date.now(); buffer = ahora - ultimoCaracter < 900 ? buffer + key : key; ultimoCaracter = ahora;
        abrir(); var consulta = normalizar(buffer); var repetido = Array.from(consulta).every(function (letra) { return letra === consulta[0]; });
        if (repetido) consulta = consulta[0];
        var inicio = repetido ? opciones.indexOf(activo) + 1 : 0;
        var orden = opciones.slice(inicio).concat(opciones.slice(0, inicio));
        var encontrado = orden.find(function (index) { return normalizar(select.options[index].textContent.trim()).indexOf(consulta) === 0; });
        if (encontrado !== undefined) activar(encontrado);
      }
    });
    select.addEventListener('change', sincronizar);
    select.addEventListener('invalid', function (e) {
      e.preventDefault(); error.textContent = select.validity.valueMissing ? 'Elige una opción para continuar.' : select.validationMessage;
      error.hidden = false; boton.setAttribute('aria-invalid', 'true'); boton.setAttribute('aria-describedby', error.id);
      if (!select.form || select.form.querySelector(':invalid') === select) boton.focus();
    });
    if (select.form) select.form.addEventListener('reset', function () { cerrar(false); setTimeout(function () { limpiarError(); sincronizar(); }, 0); });
    var dialogo = select.closest('dialog'); if (dialogo) dialogo.addEventListener('close', function () { cerrar(false); });
    document.addEventListener('pointerdown', function (e) { if (estaAbierto && !marco.contains(e.target)) cerrar(false); }, true);
    document.addEventListener('focusin', function (e) { if (estaAbierto && !marco.contains(e.target)) cerrar(false); });
    sincronizar(); select.classList.add('select-calido__nativo'); select.tabIndex = -1; select.setAttribute('aria-hidden', 'true'); label.htmlFor = boton.id;
  });
  window.addEventListener('resize', function () { if (abierto) abierto.posicionar(); });
  document.addEventListener('scroll', function () { if (abierto) abierto.posicionar(); }, true);
  if (window.visualViewport) {
    visualViewport.addEventListener('resize', function () { if (abierto) abierto.posicionar(); });
    visualViewport.addEventListener('scroll', function () { if (abierto) abierto.posicionar(); });
  }
})();
