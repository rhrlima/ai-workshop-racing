# Módulo `car-renderer.js`

Renderizador de referência do carro. Zero dependências, sem DOM; usado pela garagem (a tela de corrida do servidor tem uma cópia). Funciona no navegador (`window.CarRenderer`) e em Node (`require`).

```html
<script src="car-renderer.js"></script>
```

## API

| Função | O que faz |
|---|---|
| `CarRenderer.SCHEMA` | Descrição dos campos (tipo, intervalo, padrão, valores). Folhas têm `type`: `num`, `int`, `color` ou `enum`. Serve para gerar os controles da garagem. |
| `CarRenderer.normalize(raw)` | Valida e devolve a aparência completa (padrões preenchidos). Lança `Error` com as mesmas mensagens do servidor. `normalize({})` é o carro padrão. |
| `CarRenderer.geometry(raw)` | Dados puros: `outline` (pontos `[x, y]`), `Lf/Lm/Lr`, `h`, `cockpit`. Unidades do contrato: x em [−50, 50], y em [0, 200], nariz em y=0. |
| `CarRenderer.draw(ctx, raw, {x, y, scale, rotation})` | Desenha em um canvas 2D, nariz para cima, centrado em `(x, y)`. 1 unidade = `scale` px; `rotation` em radianos. Aceita aparência crua (normaliza antes). |

## Exemplo

```js
const ap = CarRenderer.normalize({ body: { color: "#2a9d8f", front: { shape: "round" } } });
CarRenderer.draw(ctx, ap, { x: 180, y: 240, scale: 2.2 });
```

Ordem de desenho: rodas fixas, corpo, padrão (recortado ao corpo), cockpit fixo, número. A aparência é 100% cosmética.
