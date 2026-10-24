"""15 carros de exemplo: 3 variações por atributo principal (aceleração, velocidade
máxima, dirigibilidade, frenagem e pneus). Todos usam exatamente 100 pontos.

Uso: python3 sample_cars.py [--url http://localhost:8765]   (envia ao servidor)
"""
import argparse
import json
import urllib.request

# (equipe, atributo principal, acel, vel, dir, freio, pneus, curva, cor, cor do padrão, usa padrão, número)
_ROWS = [
    ("Arranque",     "acceleration", 50, 10, 15, 15, 10, "low_end_torque", "#e63946", "#ffffff", True,  11),
    ("Largada",      "acceleration", 50, 20, 10, 10, 10, "linear",         "#ff6b35", "#222222", False, 12),
    ("Explosão",     "acceleration", 45,  5, 20, 20, 10, "low_end_torque", "#f72585", "#ffd60a", True,  13),
    ("Míssil",       "topSpeed",     20, 50,  5, 20,  5, "top_end_power",  "#3a86ff", "#ffffff", True,  21),
    ("Bala",         "topSpeed",     10, 50, 10, 25,  5, "top_end_power",  "#4361ee", "#caf0f8", False, 22),
    ("Flecha",       "topSpeed",     25, 45,  5, 15, 10, "linear",         "#4cc9f0", "#03045e", True,  23),
    ("Gato",         "handling",     20, 10, 50, 10, 10, "linear",         "#06d6a0", "#073b4c", True,  31),
    ("Aranha",       "handling",     15, 15, 45, 15, 10, "low_end_torque", "#2a9d8f", "#e9c46a", False, 32),
    ("Slalom",       "handling",     10, 20, 50, 10, 10, "top_end_power",  "#80ed99", "#22577a", True,  33),
    ("Âncora",       "braking",      15, 30,  0, 50,  5, "top_end_power",  "#8338ec", "#ffffff", True,  41),
    ("Freio de Mão", "braking",      10, 40,  5, 40,  5, "top_end_power",  "#b5179e", "#ffd6ff", False, 42),
    ("Última Hora",  "braking",      20, 25,  0, 50,  5, "linear",         "#7209b7", "#f1c0e8", True,  43),
    ("Maratona",     "tires",        15, 15, 10, 10, 50, "linear",         "#ffbe0b", "#222222", True,  51),
    ("Resistente",   "tires",        10, 20, 15, 15, 40, "linear",         "#fb8500", "#ffffff", False, 52),
    ("Fôlego",       "tires",        10, 20, 10, 10, 50, "top_end_power",  "#90be6d", "#264653", True,  53),
]

_ENDS = ["pointed", "round", "chamfer", "rounded_corners", "flat"]
_MIDS = ["rect", "waisted", "bulge"]
_PATTERNS = ["center", "double", "side", "checker", "chevron", "dots"]


def _appearance(i, color, stripe, has_pattern, num):
    return {
        "body": {"color": color,
                 "front": {"shape": _ENDS[i % 5]},
                 "middle": {"shape": _MIDS[i % 3]},
                 "rear": {"shape": _ENDS[(i * 2 + 4) % 5]}},
        "pattern": {"style": _PATTERNS[i % 6] if has_pattern else "none", "color": stripe},
        "number": {"value": num},
    }


CARS = []
for i, (t, main, ac, sp, hd, br, ti, curve, color, stripe, has_pattern, num) in enumerate(_ROWS):
    assert ac + sp + hd + br + ti == 100, t
    CARS.append({
        "team": t, "main": main,
        "points_acceleration": ac, "points_top_speed": sp, "points_handling": hd,
        "points_braking": br, "points_tires": ti, "acceleration_curve": curve,
        "appearance": _appearance(i, color, stripe, has_pattern, num),
    })


def post(url, car):
    body = {k: v for k, v in car.items() if k != "main"}
    req = urllib.request.Request(url + "/car", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8765")
    args = ap.parse_args()
    for c in CARS:
        r = post(args.url, c)
        print(f"{c['team']:<14} {c['main']:<13} {'ok' if r.get('accepted') else r.get('error')}")
