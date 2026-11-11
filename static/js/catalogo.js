(function () {
  function formatoClp(valor) {
    var entero = Number(valor);
    if (!isFinite(entero)) return "Consultar precio";
    return "$" + Math.round(entero).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function montoDe(control) {
    if (!control) return null;
    if (control.getAttribute("data-precio-pendiente") === "1" || control.getAttribute("data-pendiente") === "1") {
      return null;
    }
    var texto = control.getAttribute("data-precio");
    if (texto === null || texto === "") return null;
    var entero = Number(texto);
    return isFinite(entero) ? entero : null;
  }

  function pintar(formulario) {
    var control = formulario.querySelector("input[name='variante']:checked") || formulario.querySelector("input[name='variante']");
    var monto = montoDe(control);
    var cantidadCampo = formulario.querySelector("input[name='cantidad']");
    var cantidad = cantidadCampo ? parseInt(cantidadCampo.value, 10) : 1;
    var texto = monto === null ? "Consultar precio" : formatoClp(monto);
    var subtotal = monto === null || !isFinite(cantidad) || cantidad < 1 || cantidad > 99
      ? "Consultar precio"
      : formatoClp(monto * cantidad);
    var precio = formulario.querySelector("[data-monto-modal]");
    var suma = formulario.querySelector("[data-subtotal]");
    if (precio) {
      precio.textContent = texto;
      precio.classList.toggle("producto__precio-valor--consultar", monto === null);
    }
    if (suma) suma.textContent = subtotal;
    var tarjeta = formulario.closest("[data-producto]");
    if (!tarjeta) return;
    var visible = tarjeta.querySelector(".producto__precio [data-precio-visible]");
    if (!visible) return;
    visible.textContent = texto;
    visible.classList.toggle("producto__precio-valor--consultar", monto === null);
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-selector]"), function (formulario) {
    pintar(formulario);
    formulario.addEventListener("change", pintar.bind(null, formulario));
    formulario.addEventListener("input", pintar.bind(null, formulario));
  });

  Array.prototype.forEach.call(document.querySelectorAll("[data-abrir-selector]"), function (boton) {
    boton.addEventListener("click", function () {
      var dialogo = document.getElementById(boton.getAttribute("data-abrir-selector"));
      if (!dialogo || typeof dialogo.showModal !== "function") return;
      Array.prototype.forEach.call(document.querySelectorAll("dialog[open]"), function (otro) {
        if (otro !== dialogo) otro.close();
      });
      dialogo._origen = boton;
      dialogo.showModal();
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll("dialog.selector"), function (dialogo) {
    dialogo.addEventListener("click", function (evento) {
      if (evento.target !== dialogo) return;
      var rect = dialogo.getBoundingClientRect();
      if (evento.clientX < rect.left || evento.clientX > rect.right || evento.clientY < rect.top || evento.clientY > rect.bottom) dialogo.close();
    });
    dialogo.addEventListener("cancel", function (evento) {
      evento.preventDefault();
      dialogo.close();
    });
    dialogo.addEventListener("close", function () {
      if (dialogo._origen && typeof dialogo._origen.focus === "function") dialogo._origen.focus();
    });
    var cerrar = dialogo.querySelector("[data-cerrar-selector]");
    if (cerrar) cerrar.addEventListener("click", function () { dialogo.close(); });
    dialogo.addEventListener("keydown", function (evento) {
      if (evento.key !== "Escape" || !dialogo.open) return;
      evento.preventDefault();
      dialogo.close();
    });
  });

  function normalizar(texto) {
    return (texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  var buscador = document.querySelector("[data-buscar-productos]");
  if (!buscador) return;
  var aviso = document.querySelector("[data-sin-resultado]");
  var limpiar = document.querySelector("[data-limpiar-busqueda]");
  var menuBoton = document.querySelector("[data-categorias-toggle]");
  var navegacion = document.querySelector(".catalogo-nav");
  var todos = document.querySelector("[data-catalogo-todos]");
  var navegando = false;
  var marco = 0;

  function medirBarra() {
    var cabecera = document.querySelector(".cabecera");
    var barra = document.querySelector(".catalogo-barra");
    if (cabecera) {
      document.documentElement.style.setProperty("--cabecera-alto", cabecera.offsetHeight + "px");
    }
    if (barra) {
      document.documentElement.style.setProperty("--barra-alto", barra.offsetHeight + "px");
    }
  }

  function etiquetaDe(enlace) {
    if (!enlace) return "Todas las categorías";
    var largo = enlace.querySelector(".catalogo-nav__largo");
    return (largo ? largo.textContent : enlace.textContent).replace(/\s+/g, " ").trim();
  }

  function marcar(enlace) {
    Array.prototype.forEach.call(document.querySelectorAll(".catalogo-nav a"), function (otro) {
      if (otro === enlace) otro.setAttribute("aria-current", "location");
      else otro.removeAttribute("aria-current");
    });
    if (menuBoton) menuBoton.setAttribute("aria-label", "Categorías. " + etiquetaDe(enlace));
  }

  function cerrarMenu(devolverFoco) {
    if (!menuBoton || !navegacion) return;
    var abierto = menuBoton.getAttribute("aria-expanded") === "true";
    menuBoton.setAttribute("aria-expanded", "false");
    navegacion.classList.remove("catalogo-nav--abierto");
    if (devolverFoco && abierto) menuBoton.focus();
  }

  function sincronizarActiva() {
    if (navegando) return;
    var barra = document.querySelector(".catalogo-barra");
    var limite = (barra ? barra.getBoundingClientRect().bottom : 0) + 160;
    var activa = null;
    Array.prototype.forEach.call(document.querySelectorAll(".catalogo-grupo"), function (grupo) {
      if (grupo.hidden) return;
      var titulo = grupo.querySelector("h2");
      if (titulo && titulo.getBoundingClientRect().top <= limite) activa = grupo;
    });
    if (!activa) {
      marcar(todos);
      return;
    }
    var enlace = document.querySelector('.catalogo-nav a[href="#' + activa.id + '"]');
    if (enlace && !enlace.hidden) marcar(enlace);
  }

  function filtrar() {
    var consulta = normalizar(buscador.value.trim());
    var visibles = 0;
    Array.prototype.forEach.call(document.querySelectorAll(".catalogo-grupo"), function (grupo) {
      var cantidad = 0;
      Array.prototype.forEach.call(grupo.querySelectorAll("[data-producto]"), function (tarjeta) {
        var coincide = !consulta || normalizar(tarjeta.getAttribute("data-busqueda")).indexOf(consulta) !== -1;
        tarjeta.hidden = !coincide;
        if (coincide) cantidad += 1;
      });
      grupo.hidden = cantidad === 0;
      var enlace = document.querySelector('.catalogo-nav a[href="#' + grupo.id + '"]');
      if (enlace) enlace.hidden = cantidad === 0;
      visibles += cantidad;
    });
    if (aviso) aviso.hidden = visibles !== 0;
    if (limpiar) limpiar.hidden = consulta === "";
    sincronizarActiva();
  }

  buscador.addEventListener("input", filtrar);
  if (limpiar) {
    limpiar.addEventListener("click", function () {
      buscador.value = "";
      filtrar();
      buscador.focus();
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll(".catalogo-nav a"), function (enlace) {
    enlace.addEventListener("click", function (evento) {
      var destino = document.getElementById((enlace.getAttribute("href") || "").slice(1));
      if (destino && destino.hidden) {
        evento.preventDefault();
        cerrarMenu(false);
        return;
      }
      navegando = true;
      marcar(enlace);
      cerrarMenu(false);
      window.setTimeout(function () { navegando = false; sincronizarActiva(); }, 900);
    });
  });
  if (menuBoton && navegacion) {
    menuBoton.addEventListener("click", function () {
      var abrir = menuBoton.getAttribute("aria-expanded") !== "true";
      menuBoton.setAttribute("aria-expanded", abrir ? "true" : "false");
      navegacion.classList.toggle("catalogo-nav--abierto", abrir);
    });
    document.addEventListener("click", function (evento) {
      if (menuBoton.contains(evento.target) || navegacion.contains(evento.target)) return;
      cerrarMenu(false);
    });
    document.addEventListener("keydown", function (evento) {
      if (evento.key !== "Escape" || document.querySelector("dialog[open]")) return;
      cerrarMenu(true);
    });
  }
  medirBarra();
  if (window.ResizeObserver) {
    var observador = new ResizeObserver(medirBarra);
    var cabecera = document.querySelector(".cabecera");
    var barra = document.querySelector(".catalogo-barra");
    if (cabecera) observador.observe(cabecera);
    if (barra) observador.observe(barra);
  }
  window.addEventListener("scroll", function () {
    if (marco) return;
    marco = window.requestAnimationFrame(function () {
      marco = 0;
      sincronizarActiva();
    });
  }, { passive: true });
})();
