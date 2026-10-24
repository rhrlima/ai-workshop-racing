"""Servidor HTTP da simulação.

Endpoints:
  POST /car    {team, points_acceleration, points_top_speed, points_handling,
                points_braking, points_tires (opcional), acceleration_curve}  -> valida e registra a equipe
               (também aceita o JSON gerado pelo cliente Garagem)
  GET  /teams  -> equipes registradas
  POST /race   {"track": "interlagos_lite", "laps": 5} (opcionais) -> roda a corrida
  GET  /tracks -> pistas disponíveis
  POST /car/validate  (mesmo corpo de /car) -> {valid, car | error}, sem registrar
  POST /simulate {car, track?, laps?} -> tempo e velocidade média de uma corrida solo (sem registrar)
  POST /cars/random {"count": 10} -> registra carros aleatórios (para testes)

Uso: python3 main.py [--port 8765] [--demo] [--multi-tabs | --no-multi-tabs] [--random-cars N]

  --multi-tabs (padrão): cada aba/equipe com um nome diferente entra na corrida como um carro.
  --no-multi-tabs: só existe um carro; um novo envio (de qualquer aba) substitui o anterior.
  GET /config informa o modo atual.
"""
import argparse
import json
import random
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from collections import deque
from threading import Lock

import physics
import race_engine
import track_manager

MAX_BODY = 16 * 1024
MAX_TEAMS = 64
MAX_FRAMES = 3000
MAX_RANDOM = 50
RATE_WINDOW = 60                       # segundos
RATE_LIMIT_GENERAL = 120               # POSTs por janela, por IP
RATE_LIMIT_HEAVY = 60                  # POSTs pesados por janela, por IP
HEAVY_PATHS = {"/race", "/simulate"}


class RateLimiter:
    """Janela deslizante em memória, por chave (IP + categoria)."""

    def __init__(self, window):
        self.window = window
        self.hits = {}
        self.lock = Lock()
        self.last_prune = time.monotonic()

    def check(self, key, limit):
        """Retorna 0 se permitido; senão, segundos até poder tentar de novo."""
        now = time.monotonic()
        with self.lock:
            if now - self.last_prune > self.window:
                for k in [k for k, q in self.hits.items() if not q or now - q[-1] > self.window]:
                    del self.hits[k]
                self.last_prune = now
            q = self.hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(self.window - (now - q[0])) + 1)
            q.append(now)
            return 0


LIMITER = RateLimiter(RATE_WINDOW)
TEAMS = {}
OWNERS = {}            # team -> IP de origem (usado no modo --no-multi-tabs)
SETTINGS = {"multi_tabs": True}
LOCK = Lock()          # a simulação imprime no console; uma corrida por vez
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
STATIC = {"/": "race.html", "/race.html": "race.html", "/style.css": "style.css",
          "/race.js": "race.js", "/car-renderer.js": "car-renderer.js"}
MIME = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}


def render_info(car):
    """Dados que o renderizador da corrida precisa: atributos + aparência do JSON do cliente."""
    return {
        "team": car["team"],
        "curve": car["curve"],
        "attributes": {"acceleration": car["points_acceleration"], "topSpeed": car["points_top_speed"],
                       "handling": car["points_handling"], "braking": car["points_braking"], "tires": car["points_tires"]},
        "appearance": car["appearance"],
    }


class Handler(BaseHTTPRequestHandler):
    def _client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def _send(self, code, obj, headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            raise physics.InvalidCar("corpo inválido ou grande demais")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise physics.InvalidCar("JSON malformado")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/teams":
            with LOCK:
                self._send(200, {"teams": list(TEAMS.values())})
        elif self.path == "/config":
            self._send(200, {"multi_tabs": SETTINGS["multi_tabs"], "max_teams": MAX_TEAMS})
        elif self.path == "/tracks":
            self._send(200, {"tracks": track_manager.list_tracks()})
        elif self.path in STATIC:
            name = STATIC[self.path]
            try:
                with open(os.path.join(WEB_DIR, name), "rb") as f:
                    body = f.read()
            except OSError:
                return self._send(404, {"error": "arquivo da tela de corrida não encontrado"})
            self.send_response(200)
            self.send_header("Content-Type", MIME[os.path.splitext(name)[1]] + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send(404, {"error": "não encontrado"})

    def do_POST(self):
        heavy = self.path in HEAVY_PATHS
        retry = LIMITER.check((self._client_ip(), heavy), RATE_LIMIT_HEAVY if heavy else RATE_LIMIT_GENERAL)
        if retry:
            return self._send(429, {"error": f"muitas requisições; tente novamente em {retry}s"},
                              {"Retry-After": str(retry)})
        try:
            data = self._read_json()
            if self.path == "/car":
                self._register(data)
            elif self.path == "/race":
                self._race(data)
            elif self.path == "/car/validate":
                self._validate(data)
            elif self.path == "/simulate":
                self._simulate(data)
            elif self.path == "/cars/random":
                self._random_cars(data)
            elif self.path == "/cars/clear":
                with LOCK:
                    removed = len(TEAMS)
                    TEAMS.clear()
                    OWNERS.clear()
                self._send(200, {"cleared": True, "removed": removed, "teams": 0})
            else:
                self._send(404, {"error": "não encontrado"})
        except physics.InvalidCar as e:
            if self.path == "/car/validate":
                self._send(200, {"valid": False, "error": str(e)})
            elif self.path == "/simulate":
                self._send(400, {"simulated": False, "error": str(e)})
            else:
                self._send(400, {"accepted": False, "error": str(e)})

    def _validate(self, data):
        """Só valida (mesmas regras de /car); não registra nada."""
        car = physics.validate_car(data)
        spent = sum(car[f] for f in physics.POINT_FIELDS)
        self._send(200, {"valid": True, "car": car, "points_spent": spent,
                         "points_left": physics.BUDGET - spent})

    def _simulate(self, data):
        """Corrida solo, só a lógica: não registra o carro e não devolve frames."""
        if not isinstance(data, dict) or not isinstance(data.get("car"), dict):
            raise physics.InvalidCar("envie {\"car\": {...}, \"track\": \"...\", \"laps\": N}")
        car = physics.validate_car(data["car"])
        try:
            key = data.get("track")
            if key is None:
                key = random.choice(list(track_manager.TRACKS))     # sem pista: sorteia
            track = track_manager.get_track(key, data.get("laps"))
        except (KeyError, TypeError, ValueError) as e:
            raise physics.InvalidCar(str(e.args[0]) if e.args else "pista inválida")
        r = race_engine.run_race([car], track, verbose=False)[0]
        self._send(200, {"simulated": True, "team": car["team"],
                         "track": {"key": track["key"], "name": track["name"], "laps": track["laps"],
                                   "length": track["length"]},
                         "result": {"time": r["time"], "distance": r["distance"], "avg_speed": r["avg_speed"],
                                    "avg_speed_kmh": round(r["avg_speed"] * 3.6, 1)}})

    def _register(self, data):
        label = data.get("team") or data.get("name") if isinstance(data, dict) else None
        try:
            car = physics.validate_car(data)
        except physics.InvalidCar as e:
            print(f"[GUARDRAIL] ❌ Carro rejeitado ({label or '?'}): {e}")
            raise
        with LOCK:
            ip = self.client_address[0]
            replaced = []
            if not SETTINGS["multi_tabs"]:
                # modo single: um carro por origem (IP); o último envio dessa origem vence
                if OWNERS.get(car["team"], ip) != ip:
                    raise physics.InvalidCar(f"a equipe '{car['team']}' pertence a outro cliente")
                replaced = [t for t, o in OWNERS.items() if o == ip and t != car["team"]]
                for t in replaced:
                    TEAMS.pop(t, None)
                    OWNERS.pop(t, None)
            if car["team"] not in TEAMS and len(TEAMS) >= MAX_TEAMS:
                raise physics.InvalidCar(f"limite de {MAX_TEAMS} equipes atingido")
            OWNERS[car["team"]] = ip
            TEAMS[car["team"]] = car
        print(f"[GUARDRAIL] ✅ Carro aceito: {car['team']} "
              f"(pontos usados: {sum(car[f] for f in physics.POINT_FIELDS):g}/{physics.BUDGET})")
        self._send(200, {"accepted": True, "car": car, "multi_tabs": SETTINGS["multi_tabs"],
                         "replaced": replaced, "teams": len(TEAMS)})

    def _random_cars(self, data):
        count = data.get("count", 10) if isinstance(data, dict) else 10
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_RANDOM:
            raise physics.InvalidCar(f"'count' deve ser um inteiro de 1 a {MAX_RANDOM}")
        if not SETTINGS["multi_tabs"]:
            raise physics.InvalidCar("carros aleatórios exigem --multi-tabs")
        replace = data.get("replace") is True if isinstance(data, dict) else False
        with LOCK:
            if replace:
                TEAMS.clear()
                OWNERS.clear()
            free = MAX_TEAMS - len(TEAMS)
            if free <= 0:
                raise physics.InvalidCar(f"limite de {MAX_TEAMS} equipes atingido")
            added = []
            for _ in range(min(count, free)):
                car = physics.validate_car(physics.random_car(TEAMS))
                TEAMS[car["team"]] = car
                added.append(car)
        print(f"[TESTE] 🎲 {len(added)} carros aleatórios {'no lugar dos existentes' if replace else 'adicionados'}")
        self._send(200, {"accepted": True, "added": added, "teams": len(TEAMS)})

    def _race(self, data):
        data = data if isinstance(data, dict) else {}
        key = data.get("track", track_manager.DEFAULT_TRACK)
        try:
            track = track_manager.get_track(key, data.get("laps"))
        except (KeyError, TypeError, ValueError) as e:
            raise physics.InvalidCar(str(e.args[0]) if e.args else "pista inválida")
        with LOCK:
            cars = list(TEAMS.values())
            frames = [[0.0, []]]
            results = []
            if cars:  # sem carros devolve só a pista, para a tela exibi-la
                frames = []
                results = race_engine.run_race(cars, track, verbose=not data.get("quiet"), frames=frames)
        # corridas longas: reduz a resolução dos frames para a resposta não ficar gigante
        step = max(1, -(-len(frames) // MAX_FRAMES))
        if step > 1:
            frames = frames[::step] + ([frames[-1]] if (len(frames) - 1) % step else [])
        self._send(200, {
            "track": {"name": track["name"], "description": track["description"], "laps": track["laps"], "length": track["length"],
                      "segments": track["segments"]},
            "cars": [render_info(c) for c in cars],
            "results": results,
            "frames": frames,
            "dt": race_engine.DT * step,
        })

    def log_message(self, fmt, *args):
        pass


DEMO_CARS = [
    {"team": "Equipe_Alpha", "points_acceleration": 25, "points_top_speed": 25,
     "points_handling": 25, "points_braking": 25, "acceleration_curve": "linear"},
    {"team": "Equipe_Beta", "points_acceleration": 20, "points_top_speed": 50,
     "points_handling": 10, "points_braking": 20, "acceleration_curve": "top_end_power"},
    {"team": "Equipe_Gama", "points_acceleration": 35, "points_top_speed": 10,
     "points_handling": 35, "points_braking": 20, "acceleration_curve": "low_end_torque"},
    {"team": "Equipe_Hacker", "points_acceleration": 0, "points_top_speed": 999,
     "points_handling": 0, "points_braking": 0, "acceleration_curve": "linear"},
]


def run_demo(track_key):
    cars = []
    for raw in DEMO_CARS:
        try:
            cars.append(physics.validate_car(raw))
            print(f"[GUARDRAIL] ✅ {raw['team']} aceito")
        except physics.InvalidCar as e:
            print(f"[GUARDRAIL] ❌ {raw['team']} rejeitado: {e}")
    race_engine.run_race(cars, track_manager.get_track(track_key))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="interface de escuta; use 0.0.0.0 para aceitar outras máquinas da rede")
    ap.add_argument("--demo", action="store_true", help="roda uma corrida de exemplo e sai")
    ap.add_argument("--multi-tabs", action=argparse.BooleanOptionalAction, default=True,
                    help="permite vários carros/equipes (abas) simultâneos; --no-multi-tabs mantém só o último")
    ap.add_argument("--random-cars", type=int, default=0, metavar="N",
                    help="já registra N carros aleatórios ao iniciar (teste)")
    ap.add_argument("--track", default=track_manager.DEFAULT_TRACK)
    args = ap.parse_args()
    if args.demo:
        run_demo(args.track)
    else:
        SETTINGS["multi_tabs"] = args.multi_tabs
        if args.random_cars and args.multi_tabs:
            for _ in range(min(args.random_cars, MAX_TEAMS)):
                c = physics.validate_car(physics.random_car(TEAMS))
                TEAMS[c["team"]] = c
            print(f"[TESTE] 🎲 {len(TEAMS)} carros aleatórios registrados")
        srv = ThreadingHTTPServer((args.host, args.port), Handler)
        print(f"Servidor em http://{args.host}:{args.port}  (POST /car, POST /race, GET /teams) "
              f"| multi-tabs: {'ON' if args.multi_tabs else 'OFF (um carro só)'}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nEncerrado.")
