(function () {
  var boton = document.querySelector("[data-volver-arriba]");
  if (!boton) return;

  function actualizar() {
    boton.hidden = window.scrollY < 480;
  }

  boton.addEventListener("click", function () {
    var reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reducido ? "auto" : "smooth" });
  });
  window.addEventListener("scroll", actualizar, { passive: true });
  actualizar();
})();
