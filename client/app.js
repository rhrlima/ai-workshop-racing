// Ponto de partida: apenas desenha o carro com a aparência padrão.

const ctx = document.getElementById("car-canvas").getContext("2d");
const appearance = CarRenderer.normalize({ number: { value: 7 } });

function render() {
  const { width: w, height: h } = ctx.canvas;
  ctx.clearRect(0, 0, w, h);
  CarRenderer.draw(ctx, appearance, { x: w / 2, y: h / 2, scale: 2.2 });
}

render();
