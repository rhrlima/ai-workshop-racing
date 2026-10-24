// Renderizador do carro. Standalone: sem dependências e sem DOM.

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CarRenderer = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const MODULE_VERSION = 1;
  const END_SHAPES = ["flat", "round", "pointed", "chamfer", "rounded_corners"];
  const MIDDLE_SHAPES = ["rect", "waisted", "bulge"];
  const PATTERN_STYLES = ["none", "center", "double", "side", "checker", "chevron", "dots"];

  // Seções e cockpit são fixos: comprimentos 60/80/60; cockpit círculo de 30 em (0, 110).
  const LF = 60, LM = 80, LR = 60;
  const COCKPIT = { y: 110, d: 30, color: "#222222" };
  const STRIPE_WIDTH = 14;
  const BODY_WIDTH = 70, NUMBER_COLOR = "#ffffff";

  const num = (min, max, def) => ({ type: "num", min, max, default: def });
  const int = (min, max, def) => ({ type: "int", min, max, default: def });
  const color = (def) => ({ type: "color", default: def });
  const oneOf = (values, def) => ({ type: "enum", values, default: def });

  // Mesmo esquema do contrato (docs/car-contract.md). Folha = tem "type"; grupo = objeto com folhas.
  const SCHEMA = {
    body: {
      color: color("#d62828"),
      front: { shape: oneOf(END_SHAPES, "pointed") },
      middle: { shape: oneOf(MIDDLE_SHAPES, "rect") },
      rear: { shape: oneOf(END_SHAPES, "flat") },
    },
    pattern: { style: oneOf(PATTERN_STYLES, "center"), color: color("#ffffff") },
    number: { value: int(0, 99, 0) },
  };
  const ROOT_SCHEMA = SCHEMA;

  const HEX = /^#[0-9a-fA-F]{6}$/;
  const isLeaf = (s) => typeof s.type === "string";

  function cleanLeaf(path, spec, raw) {
    if (raw === undefined || raw === null) return spec.default;
    if (spec.type === "color") {
      if (typeof raw !== "string" || !HEX.test(raw)) throw new Error(`${path}: cor deve ser '#RRGGBB'`);
      return raw.toLowerCase();
    }
    if (spec.type === "enum") {
      if (typeof raw !== "string" || !spec.values.includes(raw)) {
        throw new Error(`${path}: '${raw}' inválido; permitidos: ${spec.values.join(", ")}`);
      }
      return raw;
    }
    const ok = spec.type === "int" ? Number.isInteger(raw) : typeof raw === "number" && Number.isFinite(raw);
    if (!ok) throw new Error(`${path}: deve ser ${spec.type === "int" ? "um inteiro" : "um número"}`);
    if (raw < spec.min || raw > spec.max) throw new Error(`${path}: ${raw} fora do intervalo ${spec.min} a ${spec.max}`);
    return raw;
  }

  function cleanGroup(path, schema, raw) {
    if (raw === undefined || raw === null) raw = {};
    if (typeof raw !== "object" || Array.isArray(raw)) throw new Error(`${path}: deve ser um objeto`);
    const unknown = Object.keys(raw).filter((k) => !(k in schema));
    if (unknown.length) {
      throw new Error(`${path}: campo(s) desconhecido(s) ${unknown.join(", ")}; permitidos: ${Object.keys(schema).join(", ")}`);
    }
    const out = {};
    for (const [key, spec] of Object.entries(schema)) {
      out[key] = isLeaf(spec) ? cleanLeaf(`${path}.${key}`, spec, raw[key]) : cleanGroup(`${path}.${key}`, spec, raw[key]);
    }
    return out;
  }

  // Valida e devolve a aparência v2 completa (padrões preenchidos). Lança Error se inválida.
  function normalize(raw) {
    return cleanGroup("appearance", ROOT_SCHEMA, raw);
  }

  // Borda direita de uma ponta: pontos [meia-largura, d], d = distância a partir da junção (0..L).
  function endEdge(shape, hj, L) {
    switch (shape) {
      case "flat": return [[hj, 0], [hj, L]];
      case "round": {
        const pts = [];
        for (let i = 0; i <= 24; i++) { const t = i / 24; pts.push([hj * Math.sqrt(1 - t * t), t * L]); }
        return pts;
      }
      case "pointed": return [[hj, 0], [0, L]];
      case "chamfer": return [[hj, 0], [0.5 * hj, L]];
      default: { // rounded_corners
        const r = Math.min(0.5 * hj, L), cx = hj - r, cy = L - r;
        const pts = [[hj, 0], [hj, cy]];
        for (let i = 0; i <= 8; i++) { const a = (i / 8) * Math.PI / 2; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
        return pts;
      }
    }
  }

  // Geometria em unidades do contrato: nariz em y=0, traseira em y=200, centro em x=0.
  function geometry(raw) {
    const ap = normalize(raw), b = ap.body;
    const Lf = LF, Lm = LM, Lr = LR;
    const h = BODY_WIDTH / 2;
    const hj = b.middle.shape === "bulge" ? 0.8 * h : h;
    const hc = b.middle.shape === "waisted" ? 0.8 * h : h;

    const front = endEdge(b.front.shape, hj, Lf).map(([x, d]) => [x, Lf - d]).reverse();
    const rear = endEdge(b.rear.shape, hj, Lr).map(([x, d]) => [x, Lf + Lm + d]);
    const right = [...front, [hc, Lf + Lm / 2], ...rear];
    const outline = [...right, ...right.map(([x, y]) => [-x, y]).reverse()];
    return { appearance: ap, outline, Lf, Lm, Lr, h, cockpit: COCKPIT };
  }

  function tracePath(ctx, pts) {
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
  }

  function drawPattern(ctx, p, h) {
    ctx.fillStyle = p.color;
    const w = STRIPE_WIDTH;
    const stripes = { center: [[-w / 2, w]], double: [[-1.5 * w, w], [0.5 * w, w]], side: [[-h, w], [h - w, w]] }[p.style];
    if (stripes) for (const [x, rw] of stripes) ctx.fillRect(x, 0, rw, 200);
    else if (p.style === "checker") {
      for (let k = 0; k < 5; k++) for (let j = 0; j < 10; j++) if ((k + j) % 2 === 1) ctx.fillRect(-50 + 20 * k, 20 * j, 20, 20);
    } else if (p.style === "chevron") {
      for (let n = 1; n <= 13; n += 2) {
        const y = 20 * n;
        tracePath(ctx, [[-50, y - 50], [0, y], [50, y - 50], [50, y - 30], [0, y + 20], [-50, y - 30]]);
        ctx.fill();
      }
    } else if (p.style === "dots") {
      for (let i = 0; i < 5; i++) for (let j = 0; j < 10; j++) {
        ctx.beginPath(); ctx.arc(-40 + 20 * i, 10 + 20 * j, 4, 0, Math.PI * 2); ctx.fill();
      }
    }
  }

  // Desenha o carro de nariz para cima, centrado em (x, y). 1 unidade do contrato = `scale` px.
  // rotation em radianos (0 = nariz para cima).
  function draw(ctx, raw, opts) {
    const { x = 0, y = 0, scale = 1, rotation = 0 } = opts || {};
    const g = geometry(raw), ap = g.appearance;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rotation);
    ctx.scale(scale, scale);
    ctx.translate(0, -100);

    ctx.strokeStyle = "#999"; ctx.lineWidth = 4;
    for (const wy of [40, 160]) {
      ctx.beginPath(); ctx.moveTo(-g.h, wy); ctx.lineTo(g.h, wy); ctx.stroke();
      ctx.fillStyle = "#111";
      for (const s of [-1, 1]) ctx.fillRect(s * g.h - 7, wy - 17, 14, 34);
    }

    tracePath(ctx, g.outline);
    ctx.fillStyle = ap.body.color;
    ctx.fill();

    ctx.save();
    tracePath(ctx, g.outline);
    ctx.clip();
    drawPattern(ctx, ap.pattern, g.h);
    ctx.restore();

    ctx.fillStyle = COCKPIT.color;
    ctx.beginPath();
    ctx.arc(0, COCKPIT.y, COCKPIT.d / 2, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = NUMBER_COLOR;
    ctx.font = "bold 18px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(ap.number.value), 0, COCKPIT.y);
    ctx.restore();
  }

  return { MODULE_VERSION, SCHEMA, normalize, geometry, draw };
});
