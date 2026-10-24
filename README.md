# Workshop: AI Agents Racing

Workshop em que cada equipe monta um carro de corrida (a **garagem**, no cliente) e o envia a um **servidor de simulação**, que valida o carro, simula a corrida e exibe o resultado.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| [`client/`](client) | Garagem: tela inicial que só desenha o carro (`index.html`, `app.js`, `car-renderer.js`, `style.css`) |
| [`server/`](server) | Servidor Python (`main.py`), física e motor de corrida, tela de corrida em `web/` |
| [`server/sample_cars.json`](server/sample_cars.json) | 15 carros de exemplo (3 por atributo principal), carregados por `sample_cars.py` |
| [`docs/`](docs) | Documentação (índice abaixo) |

## Início rápido

```bash
# servidor (http://localhost:8765)
cd server
python3 main.py
python3 sample_cars.py        # opcional: envia os carros de exemplo

# garagem (http://localhost:8080)
cd client
python3 -m http.server 8080
```

Em hospedagem como o Render, o servidor usa a variável `PORT` e escuta em `0.0.0.0`.

## Documentação

| Arquivo | Descrição |
|---|---|
| [`docs/server.md`](docs/server.md) | Como executar o servidor, opções, endpoints, limite de requisições e modelo de simulação |
| [`docs/api.md`](docs/api.md) | Resumo das rotas da API |
| [`docs/car-contract.md`](docs/car-contract.md) | Contrato do JSON do carro (formato canônico, aparência, validações) |
| [`docs/car-renderer.md`](docs/car-renderer.md) | Módulo `car-renderer.js` que desenha o carro |
| [`docs/client.md`](docs/client.md) | Garagem (cliente): arquivos e como executar |
