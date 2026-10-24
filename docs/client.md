# Garagem (cliente)

Ponto de partida do workshop: uma tela com o carro já desenhado. Todo o resto é construído por você, seguindo as instruções do workshop e a documentação.

```bash
cd client
python3 -m http.server 8080      # http://localhost:8080 (também funciona abrindo index.html direto)
```

## Arquivos

- `index.html`, `app.js`: a tela, que só desenha o carro
- `car-renderer.js`: módulo pronto de desenho do carro
- `style.css`

## Documentação

- Contrato do carro: [`car-contract.md`](car-contract.md)
- Módulo de desenho: [`car-renderer.md`](car-renderer.md)
- API: [`api.md`](api.md)
