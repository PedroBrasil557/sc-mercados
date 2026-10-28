# Quanto Fica

A lista de compras da casa que sabe quanto as coisas custam em cada mercado de Blumenau.

## Estrutura

| Pasta | O que tem |
|---|---|
| `backend/` | Python: regras de negócio (R1–R16), API (FastAPI), coletor agendado e monitor de qualidade |
| `db/` | Migrações do PostgreSQL e verificações do esquema |
| `apps/mobile/` | App Expo SDK 58 (Android primeiro): esqueleto, navegação e tema. As telas completas entram depois do teste com as famílias |
| `packages/tema/` | Tokens do design (`tokens.json`) e `tema.ts`, gerado a partir do Figma |
| `docs/` | Decisões e checklist de lançamento na Google Play |

## Rodar localmente

```bash
# Banco de dados (Docker): aplica todas as migrações em ordem
cd db
docker compose -p quantofica up -d --wait
for f in migrations/*.sql; do docker compose -p quantofica exec -T banco psql -U quantofica -d quantofica -v ON_ERROR_STOP=1 < "$f"; done
docker compose -p quantofica exec -T banco psql -U quantofica -d quantofica < testar.sql

# Backend: os testes de integração usam o Postgres acima (banco quantofica_teste, recriado a cada módulo)
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # no Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check src tests

# API
export DATABASE_URL=postgresql://quantofica:local-apenas@localhost:54329/quantofica
.venv/Scripts/uvicorn quantofica.api.app:create_app --factory --reload   # documentação em http://localhost:8000/docs

# Coleta de uma rede (faz requisições reais, 1 por segundo)
.venv/Scripts/python -m quantofica.coleta.agendador --rede giassi

# App (na raiz do repositório)
npm install
npm run mobile

# Tema (depois de atualizar tokens.json a partir do Figma)
cd packages/tema && python gerar_tema.py
```

## API (v1)

| Rota | O que faz |
|---|---|
| `POST /v1/listas/{id}/operacoes` | Recebe operações do aparelho (R15). Reenviar a mesma operação não duplica |
| `GET /v1/listas/{id}/operacoes?desde=N` | Operações gravadas depois do cursor N, para os outros aparelhos se atualizarem |
| `GET /v1/listas/{id}` | Itens da lista agora, com o aviso quando alguém da casa tinha removido o item |
| `GET /v1/precos?loja_id=…&produto_id=…` | Preço atual de cada produto na loja (R5, R6) |
| `POST /v1/comparar` | Total da lista na loja mais próxima de cada rede e a melhor divisão entre duas (R7, R8, R13, R14) |

Ainda sem autenticação: a identificação do aparelho e da conta (R16) entra antes de qualquer publicação.

## Coleta agendada

`.github/workflows/coleta.yml` roda todo dia às 5h e na quinta à tarde. Fica desligada até existir o banco de
produção (variável `COLETA_ATIVA=true` e segredo `DATABASE_URL`). A cada rodada:

- só o preço simulado na loja física vira observação (o de catálogo é regional);
- embalagem múltipla, loja não cadastrada e preço mais de 50% longe da mediana vão para a fila de revisão;
- o monitor de qualidade confere se alguma rede está sem coleta há mais de 26 h, se a cobertura caiu mais de 10%
  e se o mesmo EAN aparece com tamanhos diferentes entre redes.

## Regras do projeto

- Toda regra de negócio tem teste com casos reais (preços da coleta de 22/10/2026).
- O coletor respeita robots.txt e no máximo 1 requisição por segundo, e nunca contorna bloqueios.
- Nenhum dado de CPF é guardado ou transmitido. Os cupons guardam só o hash da chave de acesso.
- Os agentes de IA só propõem; quem decide o que é publicado são as regras (`backend/src/quantofica/regras`).
