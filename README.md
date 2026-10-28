# Quanto Fica

A lista de compras da casa que sabe quanto as coisas custam em cada mercado de Blumenau.

## Estrutura

| Pasta | O que tem |
|---|---|
| `backend/` | Python: regras de negócio (R1–R16), coleta de preços, depois API e agentes |
| `db/` | Migrações do PostgreSQL e verificações do esquema |
| `packages/tema/` | Tokens do design (`tokens.json`) e `tema.ts`, gerado a partir do Figma |
| `docs/` | Decisões e checklist de lançamento na Google Play |
| `apps/mobile/` | (próximo passo) App Expo SDK 58 |

## Rodar localmente

```bash
# Testes do backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # no Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check src tests

# Banco de dados (Docker)
cd db
docker compose -p quantofica up -d --wait
docker compose -p quantofica exec -T banco psql -U quantofica -d quantofica < migrations/0001_inicial.sql
docker compose -p quantofica exec -T banco psql -U quantofica -d quantofica < testar.sql

# Tema (depois de atualizar tokens.json a partir do Figma)
cd packages/tema && python gerar_tema.py
```

## Regras do projeto

- Toda regra de negócio tem teste com casos reais (preços da coleta de 22/10/2026).
- O coletor respeita robots.txt e no máximo 1 requisição por segundo, e nunca contorna bloqueios.
- Nenhum dado de CPF é guardado ou transmitido. Os cupons guardam só o hash da chave de acesso.
- Os agentes de IA só propõem; quem decide o que é publicado são as regras (`backend/src/quantofica/regras`).
