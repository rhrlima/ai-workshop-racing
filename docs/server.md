# Servidor de simulação

Servidor Python que valida os carros (guardrails), simula a corrida em ticks de 0,1 s e serve a **tela de corrida** (`web/`).

## Executando

```bash
cd server
python3 main.py                       # http://localhost:8765
python3 main.py --port 9000
python3 main.py --host 0.0.0.0        # aceita clientes de outras máquinas da rede
python3 main.py --no-multi-tabs       # um carro por cliente (IP); novo envio do mesmo IP substitui o anterior
python3 main.py --random-cars 10      # já inicia com 10 carros aleatórios
python3 main.py --demo --track speedway   # corrida de exemplo no console e sai
python3 sample_cars.py                # envia os 15 carros de sample_cars.json (3 por atributo)
```

- Corrida: <http://localhost:8765/> (ou `/race.html`)

## Endpoints

Todas as respostas são JSON (UTF-8), com CORS aberto (`Access-Control-Allow-Origin: *`). Corpo máximo: 16 KiB.

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/car` | Valida e registra um carro |
| `POST` | `/car/validate` | Só valida um carro, sem registrar |
| `POST` | `/simulate` | Corrida solo (só a lógica): tempo e velocidade média, sem registrar |
| `POST` | `/cars/random` | Registra carros aleatórios (teste) |
| `POST` | `/cars/clear` | Remove todos os carros registrados (reset) |
| `GET` | `/teams` | Lista os carros registrados |
| `GET` | `/config` | Configuração do servidor |
| `GET` | `/tracks` | Lista as pistas |
| `POST` | `/race` | Roda a corrida e devolve o replay |
| `GET` | `/`, `/race.html`, `/style.css`, `/race.js`, `/car-renderer.js` | Tela de corrida (`web/`) |

### `POST /car`

Registra um carro. O corpo segue o [contrato do carro](car-contract.md) (formato canônico `points_*` ou o JSON da garagem).

```bash
curl -X POST localhost:8765/car -d '{
  "team": "Alpha", "points_acceleration": 20, "points_top_speed": 20,
  "points_handling": 20, "points_braking": 20, "points_tires": 20,
  "acceleration_curve": "linear"
}'
```

- `200`: `{"accepted": true, "car": {...}, "multi_tabs": true, "replaced": [], "teams": 1}`
- `400`: `{"accepted": false, "error": "..."}`

Reenviar o mesmo `team` substitui o carro. Limite de 64 equipes. Com `--no-multi-tabs`, cada cliente (IP de origem) mantém só um carro: um novo envio do mesmo IP substitui o anterior (`replaced` lista os removidos) e carros de outros IPs são preservados. Usar um `team` que pertence a outro IP retorna `400`. Sem `--no-multi-tabs`, um mesmo IP pode registrar vários carros (testes).

### `POST /car/validate`

Aplica exatamente as mesmas regras de `/car`, mas **não registra nada** e não consome o limite de equipes. Responde sempre `200`, inclusive para JSON malformado.

- Válido: `{"valid": true, "car": {...}, "points_spent": 80, "points_left": 20}`. `car` é o carro já normalizado e sanitizado.
- Inválido: `{"valid": false, "error": "orçamento excedido: 110 > 100 pontos"}`

### `POST /simulate`

Simula **uma corrida solo** do carro enviado, numa pista, e devolve só o resultado (tempo e velocidade média, como no resultado final). Não registra o carro, não usa o limite de equipes e não devolve frames. Serve para refinar o carro antes de enviá-lo de verdade.

```bash
curl -X POST localhost:8765/simulate -d '{"car": {"team": "Alpha", "points_acceleration": 20,
  "points_top_speed": 20, "points_handling": 20, "points_braking": 20, "points_tires": 20,
  "acceleration_curve": "linear"}, "track": "endurance", "laps": 6}'
```

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `car` | objeto | obrigatório | carro no [contrato](car-contract.md); passa pelas mesmas validações de `/car` |
| `track` | string | opcional: se omitida, **sorteia uma pista** | chave de `/tracks` |
| `laps` | inteiro 1–20 | opcional: voltas padrão da pista | número de voltas |

- `200`: `{"simulated": true, "team", "track": {"key", "name", "laps", "length"} (a pista usada, útil quando foi sorteada), "result": {"time", "distance", "avg_speed", "avg_speed_kmh"}}`. `time` (s) é `null` se o carro não terminou; `avg_speed` é em m/s.
- `400`: `{"simulated": false, "error": "..."}` (carro inválido, pista desconhecida ou `laps` inválido).

### `POST /cars/random`

Gera e registra carros aleatórios válidos, para testes.

```bash
curl -X POST localhost:8765/cars/random -d '{"count": 10}'
```

- `count`: inteiro de 1 a 50 (padrão `10`).
- `replace`: `true` remove os carros existentes antes de gerar (padrão `false`, só adiciona). É o que o botão 🎲 da tela de corrida usa.
- `200`: `{"accepted": true, "added": [...], "teams": 13}`. Se faltar espaço, adiciona só até o limite de 64 equipes.
- `400`: `count` inválido, limite de equipes atingido ou servidor em `--no-multi-tabs`.

### `POST /cars/clear`

Remove todos os carros registrados. Corpo ignorado (pode ser `{}`). `200`: `{"cleared": true, "removed": 13, "teams": 0}`. Na tela de corrida é o botão 🗑.

### `GET /teams`

`{"teams": [ {carro}, ... ]}`, na ordem de registro.

### `GET /config`

`{"multi_tabs": true, "max_teams": 64}`

### `GET /tracks`

`{"tracks": [{"key", "name", "description", "favors", "laps", "wear"}, ...]}`

| Chave | Favorece | Voltas | Desgaste |
|---|---|---|---|
| `interlagos_lite` (padrão) | equilíbrio | 3 | 1,0 |
| `speedway` | velocidade máxima | 2 | 0,2 |
| `technical` | dirigibilidade | 3 | 0,5 |
| `sprint` | aceleração | 3 | 0,3 |
| `stop_and_go` | frenagem | 3 | 0,3 |
| `endurance` | pneus | 6 | 2,5 |

### `POST /race`

Roda a corrida com todos os carros registrados. Sem carros, responde `200` só com a pista (`cars` e `results` vazios).

```bash
curl -X POST localhost:8765/race -d '{"track": "endurance", "laps": 8, "quiet": true}'
```

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `track` | string | `interlagos_lite` | chave de `/tracks` |
| `laps` | inteiro 1–20 | voltas da pista | número de voltas |
| `quiet` | boolean | `false` | `true` suprime a telemetria no console do servidor |

Resposta `200`:

```json
{
  "track": { "name", "description", "laps", "length", "segments": [ { "type", "length", "radius?", "dir?", "label" } ] },
  "cars": [ { "team", "curve", "attributes": { "acceleration", "topSpeed", "handling", "braking", "tires" }, "appearance": { } } ],
  "results": [ { "position", "team", "time", "distance", "avg_speed" } ],
  "frames": [ [ t, [ [dist, velocidade, status], ... ] ], ... ],
  "dt": 0.1
}
```

- `results` está em ordem de chegada. `time` (s) é `null` se o carro não terminou. `avg_speed` é em m/s.
- `frames`: um por tick, com os carros na mesma ordem de `cars`. Em corridas longas são reduzidos a no máximo 3000, e `dt` passa a ser maior que 0,1 (use-o para interpolar).
- Erros `400`: `{"accepted": false, "error": "..."}` para pista desconhecida, `laps` inválido ou nenhuma equipe registrada.

As corridas rodam uma de cada vez (o servidor imprime a telemetria no console, a menos que `quiet` seja `true`).

## Limite de requisições

Por IP do cliente (usa `X-Forwarded-For` quando presente), só em `POST`: **60/min** no geral e **10/min** para `/race` e `/simulate`. Ao exceder, responde `429` com o header `Retry-After` (segundos). `GET` não é limitado. Constantes `RATE_*` em `main.py`.

## Modelo de simulação (resumo)

| Atributo | Efeito |
|---|---|
| Aceleração | `a_max = 5 + 0,3·pts` m/s² |
| Velocidade máx. | `v_max = 35 + 1,4·pts` m/s |
| Dirigibilidade | `lat = 12 + 0,08·pts`; velocidade na curva `√(lat·grip·raio)` |
| Frenagem | `b_max = 2 + 0,7·pts` m/s² |
| Pneus | reduz até 90% a perda de aderência: `grip = max(0,5, 1 − 0,1·desgaste·km·(1 − 0,9·pts/50))` |

A curva de aceleração (`linear`, `low_end_torque`, `top_end_power`) altera como a potência cai com a velocidade.
