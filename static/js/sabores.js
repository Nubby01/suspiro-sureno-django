(function () {
  var raiz = document.querySelector("[data-sabores]");
  if (!raiz) return;
  var items = Array.prototype.slice.call(raiz.querySelectorAll("[data-sabor]"));
  if (!items.length) return;
  var indice = 0;
  var aviso = raiz.querySelector("[data-sabor-indice]");
  var pista = raiz.querySelector("[data-sabor-pista]");
  var anterior = raiz.querySelector("[data-sabor-anterior]");
  var siguiente = raiz.querySelector("[data-sabor-siguiente]");

  function mostrar(nuevo) {
    if (nuevo < 0) nuevo = items.length - 1;
    if (nuevo >= items.length) nuevo = 0;
    indice = nuevo;
    items.forEach(function (item, posicion) {
      item.hidden = posicion !== indice;
    });
    if (aviso) aviso.textContent = (indice + 1) + " de " + items.length;
  }

  if (anterior) {
    anterior.addEventListener("click", function () {
      mostrar(indice - 1);
    });
  }
  if (siguiente) {
    siguiente.addEventListener("click", function () {
      mostrar(indice + 1);
    });
  }
  raiz.addEventListener("keydown", function (evento) {
    if (evento.key === "ArrowLeft") {
      evento.preventDefault();
      mostrar(indice - 1);
    } else if (evento.key === "ArrowRight") {
      evento.preventDefault();
      mostrar(indice + 1);
    }
  });

  var inicioX = null;
  if (pista) {
    pista.addEventListener("pointerdown", function (evento) {
      if (evento.pointerType === "mouse" && evento.button !== 0) return;
      inicioX = evento.clientX;
    });
    pista.addEventListener("pointerup", function (evento) {
      if (inicioX === null) return;
      var delta = evento.clientX - inicioX;
      inicioX = null;
      if (delta <= -40) mostrar(indice + 1);
      else if (delta >= 40) mostrar(indice - 1);
    });
    pista.addEventListener("pointercancel", function () {
      inicioX = null;
    });
  }

  mostrar(0);
})();
