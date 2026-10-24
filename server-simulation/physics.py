"""Guardrails de servidor e cinemática (pontos -> grandezas reais)."""
import math
import random
import re

BUDGET = 100
POINT_FIELDS = ("points_acceleration", "points_top_speed", "points_handling", "points_braking",
                "points_tires")
ALLOWED_CURVES = ("linear", "low_end_torque", "top_end_power")

# Aceita também o perfil JSON gerado pelo cliente Garagem
_CLIENT_ATTRS = {
    "acceleration": "points_acceleration",
    "topSpeed": "points_top_speed",
    "handling": "points_handling",
    "braking": "points_braking",
    "tires": "points_tires",
}
_CLIENT_CURVES = {
    "linear": "linear",
    "smooth": "linear",
    "aggressive": "low_end_torque",
    "progressive": "top_end_power",
}


class InvalidCar(Exception):
    pass


def normalize_payload(data):
    """Converte o formato do cliente para o formato do servidor (sem confiar em nada)."""
    if not isinstance(data, dict):
        raise InvalidCar("payload deve ser um objeto JSON")
    out = dict(data)
    attrs = data.get("attributes")
    if isinstance(attrs, dict):
        for src, dst in _CLIENT_ATTRS.items():
            if src in attrs:
                out.setdefault(dst, attrs[src])
    curve = data.get("curve")
    if isinstance(curve, dict) and "acceleration_curve" not in out:
        out["acceleration_curve"] = _CLIENT_CURVES.get(curve.get("preset"), curve.get("preset"))
    if "team" not in out and "name" in out:
        out["team"] = out["name"]
    return out


def validate_car(data):
    """Retorna um carro validado ou levanta InvalidCar."""
    data = normalize_payload(data)
    team = data.get("team")
    if not isinstance(team, str) or not team.strip() or len(team) > 32:
        raise InvalidCar("'team' deve ser um texto de 1 a 32 caracteres")

    points = {}
    for field in POINT_FIELDS:
        v = data.get(field)
        if v is None and field == "points_tires":
            v = 0       # clientes antigos não enviam pneus
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise InvalidCar(f"'{field}' ausente ou não numérico")
        if v < 0:
            raise InvalidCar(f"'{field}' não pode ser negativo ({v})")
        points[field] = v

    total = sum(points.values())
    if total > BUDGET:
        raise InvalidCar(f"orçamento excedido: {total:g} > {BUDGET} pontos")

    curve = data.get("acceleration_curve")
    if curve not in ALLOWED_CURVES:
        raise InvalidCar(f"acceleration_curve '{curve}' inválida; permitidas: {', '.join(ALLOWED_CURVES)}")

    return {"team": team.strip(), "curve": curve, **points,
            "appearance": _clean_appearance(data.get("appearance"))}


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _clean_appearance(raw):
    """Valida a aparência (contrato em docs/car-contract.md); ausente = padrões."""
    return clean_appearance_v2(raw)


# --- Aparência v2: carro em seções, 100% cosmético --------------------------------
END_SHAPES = ("flat", "round", "pointed", "chamfer", "rounded_corners")
MIDDLE_SHAPES = ("rect", "waisted", "bulge")
PATTERN_STYLES = ("none", "center", "double", "side", "checker", "chevron", "dots")

# campo -> (tipo, regra, padrão). Tipos: enum (tupla), num (min, max), int (min, max), color
_V2_SCHEMA = {
    "body": {
        "color": ("color", "#d62828"),
        "front": {"shape": ("enum", END_SHAPES, "pointed")},
        "middle": {"shape": ("enum", MIDDLE_SHAPES, "rect")},
        "rear": {"shape": ("enum", END_SHAPES, "flat")},
    },
    "pattern": {
        "style": ("enum", PATTERN_STYLES, "center"),
        "color": ("color", "#ffffff"),
    },
    "number": {
        "value": ("int", (0, 99), 0),
    },
}


def _v2_field(path, spec, raw):
    kind = spec[0]
    default = spec[-1]
    if raw is None:
        return default
    if kind == "color":
        if not (isinstance(raw, str) and _HEX.match(raw)):
            raise InvalidCar(f"{path}: cor deve ser '#RRGGBB'")
        return raw.lower()
    if kind == "enum":
        if raw not in spec[1] or not isinstance(raw, str):
            raise InvalidCar(f"{path}: '{raw}' inválido; permitidos: {', '.join(spec[1])}")
        return raw
    lo, hi = spec[1]
    ok = isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(raw)
    if kind == "int":
        ok = isinstance(raw, int) and not isinstance(raw, bool)
    if not ok:
        raise InvalidCar(f"{path}: deve ser {'um inteiro' if kind == 'int' else 'um número'}")
    if not lo <= raw <= hi:
        raise InvalidCar(f"{path}: {raw:g} fora do intervalo {lo} a {hi}")
    return raw


def _v2_clean(path, schema, raw):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise InvalidCar(f"{path}: deve ser um objeto")
    unknown = [k for k in raw if k not in schema]
    if unknown:
        raise InvalidCar(f"{path}: campo(s) desconhecido(s) {', '.join(map(str, unknown))}; "
                         f"permitidos: {', '.join(schema)}")
    out = {}
    for key, spec in schema.items():
        if isinstance(spec, dict):
            out[key] = _v2_clean(f"{path}.{key}", spec, raw.get(key))
        else:
            out[key] = _v2_field(f"{path}.{key}", spec, raw.get(key))
    return out


def clean_appearance_v2(raw):
    """Valida a aparência v2 e devolve a forma canônica COMPLETA (defaults preenchidos)."""
    return _v2_clean("appearance", _V2_SCHEMA, raw)


def car_stats(car):
    """Converte pontos em grandezas reais (SI)."""
    return {
        "a_max": 5.0 + 0.3 * car["points_acceleration"],        # m/s²
        "v_max": 35.0 + 1.4 * car["points_top_speed"],          # m/s
        "lat_g": 12.0 + 0.08 * car["points_handling"],            # m/s² laterais
        "b_max": 2.0 + 0.7 * car["points_braking"],            # m/s² desaceleração
        "tire_keep": car["points_tires"] / MAX_TIRES,       # 0..1 (resistência ao desgaste)
        "curve": car["curve"],
    }


MAX_TIRES = 50.0
WEAR_PER_KM = 0.10      # perda de aderência por km com pneus 0 em pista de desgaste 1.0
MIN_GRIP = 0.5


def tire_grip(stats, dist, wear=1.0):
    """Aderência restante (0.5..1) após `dist` metros. Pneus no máximo desgastam 90% menos."""
    loss = WEAR_PER_KM * wear * (dist / 1000.0) * (1.0 - 0.9 * min(1.0, stats["tire_keep"]))
    return max(MIN_GRIP, 1.0 - loss)


def corner_speed(stats, radius, grip=1.0):
    """Velocidade máxima numa curva: v = sqrt(a_lat * r), com a aderência atual dos pneus."""
    return math.sqrt(stats["lat_g"] * grip * radius)


def accel_at(stats, v):
    """Aceleração disponível na velocidade v conforme a curva escolhida."""
    r = min(1.0, v / stats["v_max"])
    if stats["curve"] == "low_end_torque":
        factor = 1.4 - 1.2 * r      # forte na saída, fraca em alta
    elif stats["curve"] == "top_end_power":
        factor = 0.5 + 0.4 * r      # fraca na saída, mantém fôlego em alta
    else:
        factor = 1.0 - 0.5 * r
    return stats["a_max"] * max(factor, 0.05)


def braking_distance(stats, v, v_target, grip=1.0):
    if v <= v_target:
        return 0.0
    return (v * v - v_target * v_target) / (2.0 * stats["b_max"] * grip)


_NAMES = ("Raio", "Trovão", "Falcão", "Pantera", "Cometa", "Furacão", "Tubarão", "Lobo", "Águia", "Dragão",
          "Ninja", "Tigre", "Foguete", "Jaguar", "Víbora", "Meteoro", "Titã", "Relâmpago", "Fênix", "Corisco")


def random_appearance(rng=random):
    """Aparência v2 aleatória e válida."""
    col = lambda: "#%06x" % rng.randrange(0x1000000)
    return {
        "body": {"color": col(),
                 "front": {"shape": rng.choice(END_SHAPES)},
                 "middle": {"shape": rng.choice(MIDDLE_SHAPES)},
                 "rear": {"shape": rng.choice(END_SHAPES)}},
        "pattern": {"style": rng.choice(PATTERN_STYLES), "color": col()},
        "number": {"value": rng.randint(0, 99)},
    }


def random_car(taken=(), rng=random):
    """Gera um carro aleatório válido (100 pontos, no máx. 50 por atributo) com nome único."""
    while True:
        cuts = sorted(rng.randint(0, BUDGET) for _ in range(len(POINT_FIELDS) - 1))
        pts = [b - a for a, b in zip([0] + cuts, cuts + [BUDGET])]
        if max(pts) <= 50:
            break
    while True:
        team = f"{rng.choice(_NAMES)}_{rng.randint(100, 999)}"
        if team not in taken:
            break
    car = {"team": team, "acceleration_curve": rng.choice(ALLOWED_CURVES),
           "appearance": random_appearance(rng)}
    car.update(zip(POINT_FIELDS, pts))
    return car
