"""Definição das pistas (segmentos lógicos de retas e curvas).

Cada curva pode ter "dir": -1 para virar ao contrário (cria chicanes/esses).
O cliente usa a sequência de segmentos de uma volta para desenhar o traçado.
"""


def S(length):
    return {"type": "straight", "length": length}


def C(length, radius, dir=1):
    return {"type": "corner", "length": length, "radius": radius, "dir": dir}


TRACKS = {
    "interlagos_lite": {
        "name": "Interlagos Lite",
        "description": "Equilibrada: duas retas, uma curva média e um grampo. Nenhum atributo domina.",
        "favors": ["equilíbrio"],
        "laps": 3, "wear": 1.0,
        "segments": [S(600), C(100, 35), S(400), C(100, 15)],
    },
    "speedway": {
        "name": "Speedway",
        "description": "Retas enormes e curvas largas e rápidas: vence quem tem velocidade máxima.",
        "favors": ["velocidade máxima"],
        "laps": 2, "wear": 0.2,
        "segments": [S(900), C(150, 120), S(400), C(100, 90), S(900), C(150, 120), S(400), C(100, 90)],
    },
    "technical": {
        "name": "Technical",
        "description": "Curvas fechadas em sequência com retas curtas: vence quem tem dirigibilidade.",
        "favors": ["dirigibilidade"],
        "laps": 3, "wear": 0.5,
        "segments": [S(80), C(70, 14), S(60), C(70, 14), S(90), C(60, 12, -1),
                     S(50), C(60, 12), S(70), C(70, 14), S(60), C(60, 12)],
    },
    "sprint": {
        "name": "Sprint",
        "description": "Retas curtas ligadas por curvas lentas: nunca dá para chegar à velocidade máxima, quem acelera mais sai na frente.",
        "favors": ["aceleração"],
        "laps": 3, "wear": 0.3,
        "segments": [S(120), C(40, 30), S(120), C(40, 30, -1), S(120), C(40, 30), S(120), C(40, 30, -1),
                     S(120), C(40, 30), S(120), C(40, 30, -1)],
    },
    "stop_and_go": {
        "name": "Stop & Go",
        "description": "Retas longas terminando em grampos fechados: ganha quem freia mais tarde.",
        "favors": ["frenagem"],
        "laps": 3, "wear": 0.3,
        "segments": [S(700), C(60, 4), S(600), C(60, 4, -1), S(700), C(60, 4), S(600), C(60, 4, -1)],
    },
    "endurance": {
        "name": "Endurance",
        "description": "Pista abrasiva e longa (6 voltas): os pneus perdem aderência e só os duráveis mantêm o ritmo.",
        "favors": ["pneus"],
        "laps": 6, "wear": 2.5,
        "segments": [S(250), C(120, 40), S(200), C(100, 30, -1), S(250), C(120, 40), S(150), C(100, 25)],
    },
}
DEFAULT_TRACK = "interlagos_lite"


def list_tracks():
    return [{"key": k, "name": t["name"], "description": t["description"], "favors": t["favors"],
             "laps": t["laps"], "wear": t["wear"]}
            for k, t in TRACKS.items()]


MAX_LAPS = 20


def get_track(key=DEFAULT_TRACK, laps=None):
    if key not in TRACKS:
        raise KeyError(f"pista desconhecida '{key}'; disponíveis: {', '.join(TRACKS)}")
    track = TRACKS[key]
    if laps is None:
        laps = track["laps"]
    if isinstance(laps, bool) or not isinstance(laps, int) or not 1 <= laps <= MAX_LAPS:
        raise ValueError(f"'laps' deve ser um inteiro de 1 a {MAX_LAPS}")
    # Expande as voltas em uma lista linear de segmentos com rótulos legíveis
    segs = []
    for _ in range(laps):
        counters = {"straight": 0, "corner": 0}
        for s in track["segments"]:
            counters[s["type"]] += 1
            label = ("Reta " if s["type"] == "straight" else "Curva ") + str(counters[s["type"]])
            segs.append({**s, "label": label})
    return {"key": key, "name": track["name"], "description": track["description"],
            "laps": laps, "wear": track["wear"], "segments": segs, "length": sum(s["length"] for s in segs)}
