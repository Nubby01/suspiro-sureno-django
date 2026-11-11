(function () {
  document.querySelectorAll('input[type="password"]').forEach(function (input, index) {
    var marco = document.createElement('div'); marco.className = 'clave-control';
    input.parentNode.insertBefore(marco, input); marco.appendChild(input);
    if (!input.id) input.id = 'clave-visible-' + index;
    var boton = document.createElement('button'); boton.type = 'button'; boton.className = 'clave-control__boton';
    boton.setAttribute('aria-controls', input.id); boton.setAttribute('aria-pressed', 'false');
    boton.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
    function etiqueta() { var visible = input.type === 'text'; boton.setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña'); boton.title = boton.getAttribute('aria-label'); boton.setAttribute('aria-pressed', String(visible)); }
    etiqueta(); boton.addEventListener('click', function () { input.type = input.type === 'password' ? 'text' : 'password'; etiqueta(); });
    marco.appendChild(boton);
    input.form && input.form.addEventListener('submit', function () { input.type = 'password'; etiqueta(); });
  });
  document.querySelectorAll('.notificacion').forEach(function (aviso) {
    var temporizador;
    function pausar() { clearTimeout(temporizador); }
    function cerrar() { pausar(); aviso.remove(); }
    function programar() {
      pausar();
      if (!aviso.matches(':hover') && !aviso.contains(document.activeElement)) {
        temporizador = setTimeout(cerrar, 3000);
      }
    }
    var boton = aviso.querySelector('[data-cerrar-aviso]');
    if (boton) boton.addEventListener('click', cerrar);
    aviso.addEventListener('mouseenter', pausar);
    aviso.addEventListener('mouseleave', programar);
    aviso.addEventListener('focusin', pausar);
    aviso.addEventListener('focusout', function () { setTimeout(programar, 0); });
    programar();
  });
  document.querySelectorAll('.panel .ui-boton').forEach(function (b) {
    if (b.classList.contains('ui-boton--aviso')) return;
    var texto = b.textContent.trim().toLowerCase();
    if (/^(guardar|confirmar|aprobar|crear|registrar|agregar)/.test(texto)) { b.classList.remove('ui-boton--navegacion'); b.classList.add('ui-boton--guardar'); }
    else if (/^(editar|modificar)/.test(texto)) { b.classList.remove('ui-boton--navegacion'); b.classList.add('ui-boton--editar'); }
  });
  document.querySelectorAll('.panel-form').forEach(function (form) {
    form.classList.add('formulario-amplio');
    var grupos = form.querySelector('[name="es_compra"]') ? [['insumo','Movimiento de entrada'],['es_compra','Datos de compra (opcional)'],['caducidad','Lote y caducidad (opcional)']] :
      form.querySelector('[name="rendimiento"]') ? [['producto','Producto y rendimiento'],['insumo','Ingrediente']] :
      form.querySelector('[name="password1"]') ? [['first_name','Datos de la persona'],['password1','Acceso a la cuenta']] : [];
    grupos.forEach(function (grupo) { var campo=form.querySelector('[name="'+grupo[0]+'"]'); var bloque=campo && campo.closest('.campo'); if (bloque) { var titulo=document.createElement('h2'); titulo.textContent=grupo[1]; form.insertBefore(titulo,bloque); } });
    form.querySelectorAll('.campo').forEach(function (campo) {
      if (campo.querySelector('textarea, input[name*="email"], input[name*="correo"], input[name*="referencia_imagen"]')) campo.classList.add('campo--ancho');
    });
  });
  // A cancellation remains the existing state transition; only its visual action changes.
  var estadoPedido = document.getElementById('id_estado_pedido');
  if (estadoPedido && estadoPedido.form) {
    var enviarEstado = estadoPedido.form.querySelector('button[type="submit"]');
    if (enviarEstado) {
      var textoEstado = enviarEstado.textContent; var guardaba = enviarEstado.classList.contains('ui-boton--guardar');
      function indicarCancelacion() {
        var cancela = estadoPedido.value === 'cancelado';
        enviarEstado.classList.toggle('ui-boton--aviso', cancela);
        enviarEstado.classList.toggle('ui-boton--guardar', !cancela && guardaba);
        enviarEstado.textContent = cancela ? 'Cancelar pedido' : textoEstado;
      }
      estadoPedido.addEventListener('change', indicarCancelacion); indicarCancelacion();
    }
  }
})();
