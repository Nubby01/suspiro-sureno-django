(function () {
  if (!window.HTMLDialogElement) return;
  var campos = document.querySelectorAll('input[type="date"]');
  if (!campos.length) return;
  var modal = document.createElement('dialog');
  modal.className = 'calendario';
  modal.setAttribute('aria-labelledby', 'calendario-titulo');
  modal.innerHTML = '<header><h2 id="calendario-titulo">Seleccionar fecha</h2><button type="button" data-cerrar aria-label="Cerrar calendario">×</button></header><nav aria-label="Cambiar mes"><button type="button" data-mes="-1" aria-label="Mes anterior">‹</button><p aria-live="polite" data-periodo></p><button type="button" data-mes="1" aria-label="Mes siguiente">›</button></nav><div class="calendario__semana" aria-hidden="true"><span>L</span><span>M</span><span>X</span><span>J</span><span>V</span><span>S</span><span>D</span></div><div class="calendario__dias" role="group" aria-label="Días del mes"></div><footer><button type="button" data-hoy>Hoy</button><button type="button" data-limpiar>Quitar fecha</button></footer>';
  document.body.appendChild(modal);
  var activo, origen, mes;
  var dias = modal.querySelector('.calendario__dias');
  var formato = new Intl.DateTimeFormat('es-CL', {month:'long', year:'numeric'});
  var completo = new Intl.DateTimeFormat('es-CL', {weekday:'long', day:'numeric', month:'long', year:'numeric'});
  function iso(d) { return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0'); }
  function fecha(s) { return s ? new Date(s + 'T12:00:00') : new Date(); }
  function permitido(valor) { return (!activo.min || valor >= activo.min) && (!activo.max || valor <= activo.max); }
  function validar(form) {
    if (!form) return;
    var compra = form.querySelector('[name="fecha_compra"]');
    var caducidad = form.querySelector('[name="caducidad"]');
    if (compra && caducidad) {
      caducidad.min = compra.value || '';
      caducidad.setCustomValidity(compra.value && caducidad.value && caducidad.value < compra.value ? 'La caducidad no puede ser anterior a la fecha de compra.' : '');
    }
  }
  function dibujar() {
    modal.querySelector('[data-periodo]').textContent = formato.format(mes);
    dias.replaceChildren();
    var offset = (mes.getDay()+6)%7;
    for (var i=0;i<offset;i++) dias.appendChild(document.createElement('span'));
    var total = new Date(mes.getFullYear(), mes.getMonth()+1, 0).getDate();
    for (var n=1;n<=total;n++) {
      var d = new Date(mes.getFullYear(),mes.getMonth(),n,12), valor = iso(d);
      var boton = document.createElement('button');
      boton.type='button'; boton.textContent=n; boton.dataset.fecha=valor;
      boton.disabled=!permitido(valor);
      boton.setAttribute('aria-label',completo.format(d));
      boton.setAttribute('aria-pressed',String(valor===activo.value));
      if (valor===iso(new Date())) boton.setAttribute('aria-current','date');
      dias.appendChild(boton);
    }
    modal.querySelector('[data-hoy]').disabled = !permitido(iso(new Date()));
  }
  function cerrar() { modal.close(); }
  function elegir(valor) {
    activo.value=valor;
    activo.dispatchEvent(new Event('input',{bubbles:true}));
    activo.dispatchEvent(new Event('change',{bubbles:true}));
    cerrar();
  }
  campos.forEach(function (campo) {
    var marco=document.createElement('div'); marco.className='fecha-control';
    campo.before(marco); marco.appendChild(campo);
    var boton=document.createElement('button'); boton.type='button'; boton.className='fecha-control__abrir';
    var etiqueta=campo.labels.length ? campo.labels[0].textContent.trim() : 'Fecha';
    boton.setAttribute('aria-label','Abrir calendario: '+etiqueta);
    boton.setAttribute('aria-haspopup','dialog');
    boton.innerHTML='<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18M7 15h3m4 0h3m-10 3h3"/></svg>';
    marco.appendChild(boton);
    function abrir() {
      if(campo.disabled || campo.readOnly || modal.open) return;
      activo=campo; origen=boton; validar(campo.form);
      var base=fecha(campo.value);
      if(campo.min && iso(base)<campo.min) base=fecha(campo.min);
      if(campo.max && iso(base)>campo.max) base=fecha(campo.max);
      mes=new Date(base.getFullYear(),base.getMonth(),1,12);
      modal.querySelector('h2').textContent=etiqueta;
      dibujar();modal.showModal();
      var foco=dias.querySelector('[aria-pressed="true"]:not(:disabled)') || dias.querySelector('button:not(:disabled)');
      if(foco) foco.focus();
    }
    boton.addEventListener('click', abrir);
    campo.addEventListener('click', function (evento) {
      evento.preventDefault();
      abrir();
    });
    campo.addEventListener('keydown', function (evento) {
      if (evento.key === ' ' || evento.key === 'F4' || (evento.altKey && evento.key === 'ArrowDown')) {
        evento.preventDefault();
        abrir();
      }
    });
    campo.addEventListener('input',function () { validar(campo.form); });
    campo.addEventListener('change',function () { validar(campo.form); });
    if(campo.form) campo.form.addEventListener('reset',function () { setTimeout(function () { validar(campo.form); },0); });
    validar(campo.form);
  });
  modal.querySelector('[data-cerrar]').addEventListener('click',cerrar);
  modal.addEventListener('close',function () { if(origen) origen.focus(); });
  modal.addEventListener('click',function (e) {
    if(e.target===modal) {
      var r=modal.getBoundingClientRect();
      if(e.clientX<r.left || e.clientX>r.right || e.clientY<r.top || e.clientY>r.bottom) cerrar();
    }
    var boton=e.target.closest('[data-fecha]');
    if(boton && !boton.disabled) elegir(boton.dataset.fecha);
  });
  modal.querySelectorAll('[data-mes]').forEach(function (b) { b.addEventListener('click',function () {
    mes=new Date(mes.getFullYear(),mes.getMonth()+Number(b.dataset.mes),1,12);dibujar();
  }); });
  dias.addEventListener('keydown',function(e) {
    var cambios={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7};
    if(!e.target.dataset.fecha || !(e.key in cambios)) return;
    e.preventDefault();
    var d=fecha(e.target.dataset.fecha); d.setDate(d.getDate()+cambios[e.key]);
    if(!permitido(iso(d))) return;
    mes=new Date(d.getFullYear(),d.getMonth(),1,12);dibujar();
    dias.querySelector('[data-fecha="'+iso(d)+'"]').focus();
  });
  modal.querySelector('[data-hoy]').addEventListener('click',function () { elegir(iso(new Date())); });
  modal.querySelector('[data-limpiar]').addEventListener('click',function () { elegir(''); });
})();
