"""15 carros de exemplo (sample_cars.json): 3 variações por atributo principal
(aceleração, velocidade máxima, dirigibilidade, frenagem e pneus). Todos usam exatamente 100 pontos.

Uso: python3 sample_cars.py [--url http://localhost:8765]   (envia ao servidor)
"""
import argparse
import json
import os
import urllib.request

CARS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_cars.json")


def load_cars():
    with open(CARS_FILE, encoding="utf-8") as f:
        return json.load(f)


def post(url, car):
    req = urllib.request.Request(url + "/car", json.dumps(car).encode(),
                                 {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8765")
    args = ap.parse_args()
    for c in load_cars():
        r = post(args.url, c)
        print(f"{c['team']:<14} {'ok' if r.get('accepted') else r.get('error')}")
