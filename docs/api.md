# API do servidor

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/car/validate` | Valida um carro |
| `POST` | `/simulate` | Corrida solo (só a lógica): tempo e velocidade média |

## `POST /car/validate`

Valida com o servidor se o carro enviado está correto de acordo com o contrato.

- Válido: `{"valid": true, "car": {...}, "points_spent": 80, "points_left": 20}`. `car` é o carro já normalizado e sanitizado.
- Inválido: `{"valid": false, "error": "orçamento excedido: 110 > 100 pontos"}`

## `POST /simulate`

Simula **uma corrida solo** do carro enviado, numa pista, e devolve só o resultado (tempo e velocidade média, como no resultado final).

```bash
curl -X POST localhost:8765/simulate -d '{"car": {"team": "Alpha", "points_acceleration": 20,
  "points_top_speed": 20, "points_handling": 20, "points_braking": 20, "points_tires": 20,
  "acceleration_curve": "linear"}, "track": "endurance", "laps": 6}'
```

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `car` | objeto | obrigatório | carro no [contrato](car-contract.md) |
| `track` | string | opcional: se omitida, **sorteia uma pista** | lista abaixo |
| `laps` | inteiro 1–20 | opcional: voltas padrão da pista | número de voltas |

- `200`: `{"simulated": true, "team", "track": {"key", "name", "laps", "length"} (a pista usada, útil quando foi sorteada), "result": {"time", "distance", "avg_speed", "avg_speed_kmh"}}`. `time` (s) é `null` se o carro não terminou; `avg_speed` é em m/s.
- `400`: `{"simulated": false, "error": "..."}` (carro inválido, pista desconhecida ou `laps` inválido).

## Pistas disponíveis

- endurance
- interlagos_lite
- speedway
- technical
- sprint
- stop_and_go
