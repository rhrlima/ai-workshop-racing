// Renderização da corrida: reproduz os frames de telemetria enviados pelo servidor.
// Os carros são desenhados com CarRenderer (car-renderer.js), usando atributos e aparência do JSON.

const $ = (id) => document.getElementById(id);
const canvas = $("race-canvas");
const ctx = canvas.getContext("2d");
const W = canvas.width, H = canvas.height;

let race = null;       // resposta do /race
let lapLen = 0;
let playTime = 0;      // segundos simulados
let playing = false;
let lastTs = null;
let layout = null;     // traçado da pista: pontos amostrados a cada ~2 m
const TRACK_PX = 64;   // largura da pista na tela
const LANE_PX = 15;
const MAX_LANES = 5;   // com mais carros, as faixas se repetem e os carros se sobrepõem

// Monta o traçado a partir dos segmentos de uma volta: retas andam em linha reta e
// curvas giram len/raio rad (normalizados para o traçado fechar com 360°; "dir" inverte o giro).
function buildLayout(segments) {
  const STEP = 2;
  const corners = segments.filter((s) => s.type === "corner");
  const raw = corners.map((s) => ((s.dir || 1) * s.length) / s.radius);
  const net = raw.reduce((a, b) => a + b, 0);
  const k = net > 0 ? (2 * Math.PI) / net : 1;
  let x = 0, y = 0, h = 0, ci = 0;
  const pts = [{ x, y }];
  for (const s of segments) {
    const n = Math.max(1, Math.round(s.length / STEP));
    const step = s.length / n;
    const dh = s.type === "corner" ? (raw[ci++] * k) / n : 0;
    for (let i = 0; i < n; i++) {
      h += dh / 2;
      x += Math.cos(h) * step; y += Math.sin(h) * step;
      h += dh / 2;
      pts.push({ x, y });
    }
  }
  // fecha o circuito distribuindo o erro de fechamento ao longo da volta
  const ex = x, ey = y, N = pts.length - 1;
  const P = pts.slice(0, N).map((p, i) => ({ x: p.x - (ex * i) / N, y: p.y - (ey * i) / N }));
  const xs = P.map((p) => p.x), ys = P.map((p) => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const margin = 70;
  const sc = Math.min((W - 2 * margin) / (maxX - minX || 1), (H - 2 * margin) / (maxY - minY || 1));
  const ox = (W - (maxX - minX) * sc) / 2 - minX * sc, oy = (H - (maxY - minY) * sc) / 2 - minY * sc;
  return {
    pts: P.map((p) => ({ x: p.x * sc + ox, y: p.y * sc + oy })),
    cx: W / 2, cy: H / 2,
  };
}

function pathPoint(u) {
  const P = layout.pts, N = P.length;
  const f = (((u % 1) + 1) % 1) * N;
  const i = Math.floor(f) % N, k = f - Math.floor(f);
  const a = P[i], b = P[(i + 1) % N];
  const p = P[(i - 1 + N) % N], q = P[(i + 2) % N];
  return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k, a: Math.atan2(q.y - p.y, q.x - p.x) };
}

function strokeRange(u0, u1, color, width) {
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = "butt"; ctx.lineJoin = "round";
  ctx.beginPath();
  const steps = Math.max(2, Math.ceil((u1 - u0) * layout.pts.length));
  for (let i = 0; i <= steps; i++) {
    const p = pathPoint(u0 + ((u1 - u0) * i) / steps);
    i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);
  }
  ctx.stroke();
}

function drawTrack() {
  const width = TRACK_PX;
  const lapSegs = race.track.segments.slice(0, race.track.segments.length / race.track.laps);
  let acc = 0;
  for (const s of lapSegs) {
    strokeRange(acc / lapLen, (acc + s.length) / lapLen + 0.0008, s.type === "corner" ? "#5a4636" : "#3c4048", width);
    acc += s.length;
  }
  acc = 0;
  ctx.fillStyle = "#cfcfcf"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
  for (const s of lapSegs) {
    const m = pathPoint((acc + s.length / 2) / lapLen);
    // rótulo afastado do centro do circuito, para ficar fora do asfalto
    let dx = m.x - layout.cx, dy = m.y - layout.cy;
    const d = Math.hypot(dx, dy) || 1;
    ctx.fillText(s.label, m.x + (dx / d) * (width / 2 + 16), m.y + (dy / d) * (width / 2 + 16));
    acc += s.length;
  }
  // linha de largada
  const sp = pathPoint(0);
  const nx = Math.cos(sp.a + Math.PI / 2), ny = Math.sin(sp.a + Math.PI / 2);
  ctx.strokeStyle = "#fff"; ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(sp.x - (nx * width) / 2, sp.y - (ny * width) / 2);
  ctx.lineTo(sp.x + (nx * width) / 2, sp.y + (ny * width) / 2);
  ctx.stroke();
}

function stateAt(t) {
  const frames = race.frames;
  const f = t / race.dt;
  const i = Math.min(Math.floor(f), frames.length - 1);
  const j = Math.min(i + 1, frames.length - 1);
  const k = Math.min(1, f - i);
  return {
    time: frames[i][0],
    cars: frames[i][1].map((c, idx) => {
      const n = frames[j][1][idx];
      return { dist: c[0] + (n[0] - c[0]) * k, v: c[1] + (n[1] - c[1]) * k, status: c[2] };
    }),
  };
}

function render() {
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#1f3a26"; ctx.fillRect(0, 0, W, H);
  if (!race) return;
  drawTrack();
  const st = stateAt(playTime);
  const n = race.cars.length;
  const order = st.cars.map((_, i) => i).sort((a, b) => st.cars[b].dist - st.cars[a].dist);

  const carScale = n <= 4 ? 0.14 : n <= 10 ? 0.12 : 0.1;
  // o líder é desenhado por último (por cima)
  for (const idx of [...order].reverse()) {
    const dist = Math.min(st.cars[idx].dist, race.track.length);
    const p = pathPoint((dist % lapLen) / lapLen);
    const lanes = Math.min(n, MAX_LANES);
    const off = ((idx % lanes) - (lanes - 1) / 2) * LANE_PX;
    const x = p.x + Math.cos(p.a + Math.PI / 2) * off;
    const y = p.y + Math.sin(p.a + Math.PI / 2) * off;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(p.a + Math.PI / 2);
    ctx.scale(carScale, carScale);
    CarRenderer.draw(ctx, race.cars[idx].appearance, { scale: 2.2 });
    ctx.restore();
  }

  const t = st.time;
  $("clock").textContent = `${String(Math.floor(t / 60)).padStart(2, "0")}:${(t % 60).toFixed(1).padStart(4, "0")}`;
  const byTeam = Object.fromEntries(race.results.map((r) => [r.team, r]));
  const kmh = (r) => `${(r.avg_speed * 3.6).toFixed(1)} km/h`;
  // quem já cruzou a linha mantém a ordem de chegada; os demais, por distância
  const rank = [...order].sort((a, b) => {
    const fa = finished(race.cars[a], t), fb = finished(race.cars[b], t);
    if (fa && fb) return byTeam[race.cars[a].team].position - byTeam[race.cars[b].team].position;
    if (fa !== fb) return fa ? -1 : 1;
    return st.cars[b].dist - st.cars[a].dist;
  });
  $("board").innerHTML = rank.map((idx, pos) => {
    const c = race.cars[idx], s = st.cars[idx];
    const ap = c.appearance;
    const sw = `<span class="swatch" style="background:${ap.body.color}"></span>${esc(c.team)} #${ap.number.value}`;
    if (finished(c, t)) {
      const r = byTeam[c.team];
      return `<tr><td>${pos + 1}º</td><td>${sw}</td><td>${r.time.toFixed(1)} s</td><td>média ${kmh(r)}</td></tr>`;
    }
    const lap = Math.min(race.track.laps, Math.floor(s.dist / lapLen) + 1);
    return `<tr><td>${pos + 1}º</td><td>${sw}</td><td>${s.v.toFixed(1)} m/s</td><td>V${lap} · ${esc(s.status)}</td></tr>`;
  }).join("");
}

function finished(c, t) {
  const r = race.results.find((x) => x.team === c.team);
  return r && r.time !== null && t >= r.time;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function tick(ts) {
  if (playing && race) {
    if (lastTs !== null) playTime += ((ts - lastTs) / 1000) * +$("speed").value;
    const end = race.frames[race.frames.length - 1][0];
    if (playTime >= end) { playTime = end; playing = false; }
  }
  lastTs = ts;
  render();
  requestAnimationFrame(tick);
}

async function api(path, body) {
  const base = $("api").value.trim().replace(/\/$/, "");
  const res = await fetch(base + path, body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined);
  return res.json();
}

// play=false só carrega a pista e os carros parados na largada; o play é pelo botão Correr
async function runRace(play = false) {
  $("race-msg").textContent = "";
  try {
    const data = await api("/race", { track: $("track-select").value || "interlagos_lite", laps: +$("laps").value || undefined, quiet: !play });
    if (data.error) { race = null; $("race-msg").textContent = data.error; return; }
    race = data;
    if (play && !race.cars.length) $("race-msg").textContent = "Nenhum carro registrado.";
    lapLen = race.track.length / race.track.laps;
    layout = buildLayout(race.track.segments.slice(0, race.track.segments.length / race.track.laps));
    $("race-title").textContent = `${race.track.name} — ${race.track.laps} voltas`;
    $("track-info").textContent = race.track.description;
    playTime = 0; playing = play;
  } catch (e) {
    $("race-msg").textContent = "Falha ao contatar o servidor: " + e.message;
  }
}

async function loadTracks() {
  try {
    const { tracks } = await api("/tracks");
    $("track-select").innerHTML = tracks
      .map((t) => `<option value="${esc(t.key)}" data-laps="${t.laps}" title="${esc(t.description)}">${esc(t.name)}</option>`).join("");
  } catch {
    $("track-select").innerHTML = "<option>interlagos_lite</option>";
  }
}

$("api").value = location.protocol.startsWith("http") ? location.origin : "http://localhost:8765";
$("run-btn").addEventListener("click", () => runRace(true));
$("random-btn").addEventListener("click", async () => {
  try {
    const r = await api("/cars/random", { count: 10, replace: true });
    $("race-msg").textContent = r.error || "";
    if (!r.error) runRace(false);
  } catch (e) {
    $("race-msg").textContent = "Falha ao contatar o servidor: " + e.message;
  }
});
$("clear-btn").addEventListener("click", async () => {
  if (!confirm("Remover todos os carros do servidor?")) return;
  try {
    const r = await api("/cars/clear", {});
    await runRace(false);
    $("race-msg").textContent = r.error || `${r.removed} carro(s) removido(s).`;
  } catch (e) {
    $("race-msg").textContent = "Falha ao contatar o servidor: " + e.message;
  }
});
$("play-btn").addEventListener("click", () => {
  if (race && playTime >= race.frames[race.frames.length - 1][0]) playTime = 0;
  playing = !playing;
});
$("restart-btn").addEventListener("click", () => { playTime = 0; playing = !!race; });
// Trocar de pista ou dar refresh recarrega a tela, sem iniciar a corrida
function resetLaps() {
  const opt = $("track-select").selectedOptions[0];
  $("laps").value = (opt && +opt.dataset.laps) || 2;
}
$("track-select").addEventListener("change", () => {
  localStorage.setItem("race-track", $("track-select").value);
  resetLaps();
  runRace(false);
});
$("laps").addEventListener("change", () => {
  $("laps").value = Math.max(1, Math.min(20, parseInt($("laps").value, 10) || 1));
  runRace(false);
});
loadTracks().then(() => {
  const saved = localStorage.getItem("race-track");
  if ([...$("track-select").options].some((o) => o.value === saved)) $("track-select").value = saved;
  resetLaps();
  runRace(false);
});

// Atualiza a tela (sem iniciar a corrida) quando um carro é adicionado ou alterado
let teamsSig = null;
setInterval(async () => {
  try {
    const sig = JSON.stringify((await api("/teams")).teams);
    if (teamsSig !== null && sig !== teamsSig) runRace(false);
    teamsSig = sig;
  } catch { /* servidor fora do ar: tenta de novo no próximo ciclo */ }
}, 2000);
requestAnimationFrame(tick);
