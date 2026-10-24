# Contrato do JSON do carro

## 1. Formato canônico (recomendado)

```json
{
  "team": "Equipe_Alpha",
  "points_acceleration": 20,
  "points_top_speed": 20,
  "points_handling": 20,
  "points_braking": 20,
  "points_tires": 20,
  "acceleration_curve": "linear",
  "appearance": {
    "body": {
      "color": "#d62828",
      "front":  { "shape": "pointed" },
      "middle": { "shape": "rect" },
      "rear":   { "shape": "flat" }
    },
    "pattern": { "style": "center", "color": "#ffffff" },
    "number":  { "value": 7 }
  }
}
```

### Campos

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `team` | string | sim | 1 a 32 caracteres, não pode ser só espaços (o servidor remove espaços nas pontas). É o identificador da equipe: reenviar o mesmo nome **substitui** o carro. |
| `points_acceleration` | number | sim | finito, `>= 0` |
| `points_top_speed` | number | sim | finito, `>= 0` |
| `points_handling` | number | sim | finito, `>= 0` |
| `points_braking` | number | sim | finito, `>= 0` |
| `points_tires` | number | não (padrão `0`) | finito, `>= 0` |
| `acceleration_curve` | string (enum) | sim | `"linear"`, `"low_end_torque"` ou `"top_end_power"` |
| `appearance` | objeto | não | veja abaixo |

**Regra global do orçamento:** `points_acceleration + points_top_speed + points_handling + points_braking + points_tires <= 100`.

Sobre os números:
- Valores booleanos, strings, `null`, `NaN` e `Infinity` são rejeitados.
- Decimais são aceitos, mas o recomendado é usar inteiros.
- O servidor não impõe máximo por atributo, só o orçamento de 100. A garagem de referência limita cada atributo a **50**, e é recomendável fazer o mesmo.
- Pontos não gastos são permitidos (a soma pode ser menor que 100).

### O que cada atributo faz

| Atributo | Efeito na simulação |
|---|---|
| `points_acceleration` | Aceleração máxima |
| `points_top_speed` | Velocidade máxima |
| `points_handling` | Aderência lateral, que define a velocidade nas curvas |
| `points_braking` | Desaceleração máxima |
| `points_tires` | Durabilidade dos pneus |

### Curvas de aceleração

| Valor | Comportamento |
|---|---|
| `linear` | Potência cai de forma suave com a velocidade |
| `low_end_torque` | Forte na saída, fraca em alta velocidade |
| `top_end_power` | Fraca na saída, mantém fôlego em alta velocidade |

### `appearance` (cosmético, opcional)

| Campo | Tipo | Valores / intervalo | Padrão |
|---|---|---|---|
| `body.color` | cor | `#RRGGBB` (6 dígitos, com `#`) | `#d62828` |
| `body.front.shape` | enum | `flat`, `round`, `pointed`, `chamfer`, `rounded_corners` | `pointed` |
| `body.middle.shape` | enum | `rect`, `waisted`, `bulge` | `rect` |
| `body.rear.shape` | enum | `flat`, `round`, `pointed`, `chamfer`, `rounded_corners` | `flat` |
| `pattern.style` | enum | `none`, `center`, `double`, `side`, `checker`, `chevron`, `dots` | `center` |
| `pattern.color` | cor | `#RRGGBB` | `#ffffff` |
| `number.value` | inteiro | 0 a 99 (sem booleano, sem decimal) | 0 |

Regras gerais:
- Números: finitos, sem booleano e sem texto (`number.value` deve ser inteiro).
- Cores: exatamente `#` mais 6 dígitos hexadecimais.
- **Campos desconhecidos são rejeitados** em todos os níveis (um erro de digitação não passa em silêncio).
- Cada bloco (`body`, `pattern`, `number`) deve ser um objeto, ou ser omitido.

### 7.9 Renderização

- Módulo de referência: [`car-renderer.js`](../car-renderer.js), veja [`car-renderer.md`](car-renderer.md).
