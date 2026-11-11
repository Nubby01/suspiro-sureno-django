(function () {
  var nav = document.getElementById("nav-principal");
  var boton = document.querySelector("[data-nav-toggle]");
  if (!nav || !boton) return;

  var texto = boton.querySelector("[data-nav-texto]");
  var consulta = window.matchMedia("(max-width: 1023px)");

  function aplicar(cerrado) {
    var quedaCerrado = consulta.matches && cerrado;
    nav.classList.toggle("nav--cerrado", quedaCerrado);
    boton.setAttribute("aria-expanded", quedaCerrado ? "false" : "true");
    if (texto) texto.textContent = quedaCerrado ? "Menú" : "Cerrar";
  }

  aplicar(true);

  boton.addEventListener("click", function () {
    aplicar(!nav.classList.contains("nav--cerrado"));
  });

  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && consulta.matches && !nav.classList.contains("nav--cerrado")) {
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
