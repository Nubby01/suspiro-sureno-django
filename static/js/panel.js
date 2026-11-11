(function () {
  var nav = document.getElementById("panel-nav");
  var boton = document.querySelector("[data-panel-toggle]");
  if (!nav || !boton) return;

  var texto = boton.querySelector("[data-panel-texto]");
  var consulta = window.matchMedia("(max-width: 1023px)");

  function aplicar(cerrado) {
    var quedaCerrado = consulta.matches && cerrado;
    nav.classList.toggle("panel-nav--cerrado", quedaCerrado);
    boton.setAttribute("aria-expanded", quedaCerrado ? "false" : "true");
    if (texto) texto.textContent = quedaCerrado ? "Menú" : "Cerrar";
  }

  aplicar(true);

  boton.addEventListener("click", function () {
    aplicar(!nav.classList.contains("panel-nav--cerrado"));
  });

  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && consulta.matches && !nav.classList.contains("panel-nav--cerrado")) {
      aplicar(true);
      boton.focus();
    }
  });

  if (typeof consulta.addEventListener === "function") {
    consulta.addEventListener("change", function () {
      aplicar(true);
    });
  }
})();

(function () {
  var campana = document.querySelector('[data-alertas-url]');
  if (!campana) return;
  var resumen = campana.querySelector('summary');
  var contador = campana.querySelector('.panel-notificaciones__contador');
  var lista = campana.querySelector('.panel-notificaciones__lista');
  var aviso = campana.querySelector('.panel-notificaciones__aviso');
  document.addEventListener('click', function (evento) {
    if (campana.open && !campana.contains(evento.target)) campana.open = false;
  });
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && campana.open) {
      campana.open = false;
      resumen.focus();
    }
  });
  var pendiente = false;
  function ocultarAviso() { if (aviso) aviso.remove(); }
  setTimeout(ocultarAviso, 8000);
  campana.addEventListener('toggle', function () {
    if (campana.open) { ocultarAviso(); actualizar(); }
  });
  async function actualizar() {
    if (pendiente || document.hidden) return;
    pendiente = true;
    try {
      var respuesta = await fetch(campana.dataset.alertasUrl, {
        credentials: 'same-origin', headers: {'Accept': 'application/json'}, cache: 'no-store'
      });
      if (!respuesta.ok || !respuesta.headers.get('content-type').includes('application/json')) return;
      var datos = await respuesta.json();
      if (lista.innerHTML !== datos.html) {
        var enlaceActivo = lista.contains(document.activeElement) ? document.activeElement.getAttribute('href') : null;
        lista.innerHTML = datos.html;
        if (enlaceActivo) {
          var enlaces = Array.from(lista.querySelectorAll('a'));
          var destino = enlaces.find(function (enlace) { return enlace.getAttribute('href') === enlaceActivo; });
          (destino || resumen).focus();
        }
      }
      contador.textContent = datos.cantidad;
      contador.hidden = datos.cantidad === 0;
      resumen.setAttribute('aria-label', 'Alertas de inventario: ' + datos.cantidad);
      if (!datos.cantidad) ocultarAviso();
    } catch (error) { /* Conserva las alertas visibles si no hay conexión. */ }
    finally { pendiente = false; }
  }
  window.addEventListener('focus', actualizar);
  document.addEventListener('visibilitychange', actualizar);
  setInterval(actualizar, 15000);
  actualizar();
})();
