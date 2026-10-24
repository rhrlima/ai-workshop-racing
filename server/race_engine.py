"""Loop de ticks (dt = 0.1 s) e telemetria em texto."""
import physics

DT = 0.1
LOG_EVERY = 10          # ticks (1 s)
MAX_TIME = 3600.0        # segurança contra loops infinitos


class RaceCar:
    def __init__(self, car):
        self.team = car["team"]
        self.stats = physics.car_stats(car)
        self.dist = 0.0
        self.v = 0.0
        self.seg = 0
        self.seg_start = 0.0
        self.status = "Largada"
        self.d_brake = 0.0
        self.finish_time = None


def _fmt_time(t):
    return f"[{int(t // 60):02d}:{t % 60:04.1f}s]"


def _status_line(pos, c, track, width):
    seg = track["segments"][min(c.seg, len(track["segments"]) - 1)]
    status = c.status + (f" (D_brake: {c.d_brake:.0f}m)" if c.status == "Freando" else "")
    return (f"{pos}º [{c.team}]".ljust(width + 6) +
            f": {c.dist:6.1f}m | Seg: {seg['label']:<8} | Vel: {c.v:4.1f} m/s | Status: {status}")


def _print_status(t, cars, track):
    ranked = sorted(cars, key=lambda c: (c.finish_time is None, c.finish_time or -c.dist))
    width = max(len(c.team) for c in cars)
    print(f"{_fmt_time(t)} --- STATUS DA CORRIDA ---")
    for i, c in enumerate(ranked, 1):
        print(_status_line(i, c, track, width))
    print("-" * 36)


def _step(c, track, t, events):
    segs = track["segments"]
    seg = segs[c.seg]
    remaining = c.seg_start + seg["length"] - c.dist
    st = c.stats
    g = physics.tire_grip(st, c.dist, track.get("wear", 1.0))
    b = st["b_max"] * g

    # Limite de velocidade do segmento atual e do próximo (se for curva)
    limit = st["v_max"]
    if seg["type"] == "corner":
        limit = min(limit, physics.corner_speed(st, seg["radius"], g))
    nxt = segs[c.seg + 1] if c.seg + 1 < len(segs) else None
    target = None
    if nxt and nxt["type"] == "corner":
        target = min(st["v_max"], physics.corner_speed(st, nxt["radius"], g))

    # Checagem de frenagem (considera o passo do tick para não passar do ponto)
    c.d_brake = physics.braking_distance(st, c.v, target, g) if target is not None else 0.0
    braking = target is not None and c.v > target and c.d_brake + c.v * DT >= remaining

    if braking:
        c.v = max(target, c.v - b * DT)
        c.status = "Freando"
    elif c.v > limit:
        c.v = max(limit, c.v - b * DT)
        c.status = "Freando"
    elif c.v < limit:
        c.v = min(limit, c.v + physics.accel_at(st, c.v) * DT)
        c.status = "Em Curva" if seg["type"] == "corner" else "Acelerando"
    else:
        c.status = "Em Curva" if seg["type"] == "corner" else "Vel. máxima"

    # Movimento
    c.dist += c.v * DT

    # Transição de segmento
    while c.seg < len(segs) and c.dist >= c.seg_start + segs[c.seg]["length"]:
        c.seg_start += segs[c.seg]["length"]
        c.seg += 1
        if c.seg >= len(segs):
            c.finish_time = t
            c.status = "Chegou"
            events.append(f"{_fmt_time(t)} 🏁 {c.team} cruzou a linha de chegada!")
            return
        new = segs[c.seg]
        verb = "entrou em" if new["type"] == "corner" else "saiu para"
        events.append(f"{_fmt_time(t)} {c.team} {verb} {new['label']} a {c.v:.1f} m/s")


def run_race(cars, track, verbose=True, frames=None):
    """Simula a corrida; devolve a classificação final.

    Se `frames` for uma lista, recebe [t, [[dist, vel, status], ...]] a cada tick
    (na ordem de `cars`) para a renderização.
    """
    racers = [RaceCar(c) for c in cars]
    if not racers:
        raise ValueError("nenhum carro válido para correr")
    if verbose:
        print(f"\n=== {track['name']} | {track['laps']} voltas | {track['length']} m | "
              f"{len(racers)} carros ===")
    t, tick = 0.0, 0
    while any(c.finish_time is None for c in racers) and t < MAX_TIME:
        t += DT
        tick += 1
        events = []
        for c in racers:
            if c.finish_time is None:
                _step(c, track, t, events)
        if frames is not None:
            frames.append([round(t, 1), [[round(c.dist, 2), round(c.v, 2), c.status] for c in racers]])
        if verbose:
            for e in events:
                print(e)
            if tick % LOG_EVERY == 0:
                _print_status(t, racers, track)

    ranked = sorted(racers, key=lambda c: (c.finish_time is None, c.finish_time or -c.dist))
    results = [{"position": i, "team": c.team,
                "time": round(c.finish_time, 1) if c.finish_time else None,
                "distance": round(c.dist, 1),
                "avg_speed": round(c.dist / (c.finish_time or t), 2)} for i, c in enumerate(ranked, 1)]
    if verbose:
        print("\n=== RESULTADO FINAL ===")
        for r in results:
            tm = f"{r['time']:.1f}s" if r["time"] is not None else "DNF"
            print(f"{r['position']}º {r['team']}: {tm} | Vel. média: {r['avg_speed']:.1f} m/s "
                  f"({r['avg_speed'] * 3.6:.1f} km/h)")
        print()
    return results
