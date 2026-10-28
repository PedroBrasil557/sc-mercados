# SC Mercados

> Nome do projeto no código: `quantofica` (nome provisório anterior). O nome que aparece para as pessoas é **SC Mercados**.

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
# Dados iniciais: bairros e lojas de Blumenau, categorias e o catálogo das cestas validadas
for f in dados/*.sql; do docker compose -p quantofica exec -T banco psql -U quantofica -d quantofica -q < "$f"; done

# Backend: os testes de integração usam o Postgres acima (banco quantofica_teste, recriado a cada módulo)
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # no Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/ruff check src tests

# API
export DATABASE_URL=postgresql://quantofica:local-apenas@localhost:54329/quantofica
.venv/Scripts/uvicorn quantofica.api.app:create_app --factory --reload   # documentação em http://localhost:8000/docs

# Regerar os dados iniciais (consulta as redes e o OpenStreetMap)
.venv/Scripts/python scripts/gerar_cadastro_blumenau.py
.venv/Scripts/python scripts/gerar_catalogo_inicial.py

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
| `GET /v1/bairros` | Bairros da cidade (pública: vem antes do cadastro) |
| `POST /v1/aparelhos` | Primeira abertura: cria a casa, o membro e a lista, e devolve o token do aparelho |
| `POST /v1/casa/convites` | Código para a família entrar na casa (48 h, até 10 entradas) |
| `POST /v1/convites/{codigo}` | Outro aparelho entra na casa e recebe o próprio token |
| `GET /v1/eu` / `DELETE /v1/eu` | Dados da casa / exclusão da conta (LGPD art. 18, Google Play) |
| `POST /v1/listas/{id}/operacoes` | Recebe operações do aparelho (R15). Reenviar a mesma operação não duplica |
| `GET /v1/listas/{id}/operacoes?desde=N` | Operações gravadas depois do cursor N, para os outros aparelhos se atualizarem |
| `GET /v1/listas/{id}` | Itens da lista agora, com o aviso quando alguém da casa tinha removido o item |
| `GET /v1/precos?loja_id=…&produto_id=…` | Preço atual de cada produto na loja (R5, R6) |
| `POST /v1/comparar` | Total da lista na loja mais próxima de cada rede e a melhor divisão entre duas (R7, R8, R13, R14) |

Todas as rotas, menos bairros, cadastro e convite, pedem `Authorization: Bearer <token>`. Lista de outra casa responde 404.
A conta opcional (e-mail/Google, R16) entra depois; até lá o token do aparelho identifica o membro.

## Coleta agendada

O processo `coletor` (ver `fly.toml`) roda `python -m quantofica.coleta.relogio`: coleta todo dia às 5h e na quinta às
15h (Brasília), quando os encartes entram nos sites. A cada rodada:

- só o preço simulado na loja física vira observação (o de catálogo é regional);
- embalagem múltipla, loja não cadastrada e preço mais de 50% longe da mediana vão para a fila de revisão;
- o monitor de qualidade confere se alguma rede está sem coleta há mais de 26 h, se a cobertura caiu mais de 10%
  e se o mesmo EAN aparece com tamanhos diferentes entre redes.

## Publicar (Supabase + Fly.io, região São Paulo)

Uma vez, por quem é dono das contas:

1. **Supabase** (supabase.com, entrar com o GitHub): *New project* → região **South America (São Paulo)** → guarde a senha
   do banco. Em *Connect* → *Session pooler*, copie a URL `postgresql://postgres.<ref>:<senha>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres`.
2. **Fly.io** (fly.io, cadastro com cartão; duas máquinas pequenas sempre ligadas, API e coletor, dão cerca de US$ 7 por mês):
   instale o `flyctl` (`iwr https://fly.io/install.ps1 -useb | iex` no PowerShell) e rode `fly auth login`.
3. Na raiz do repositório:

```bash
fly apps create sc-mercados-api
fly secrets set DATABASE_URL="<URL do passo 1>"
fly deploy            # roda as migrações e os dados iniciais antes de subir a API e o coletor
fly status            # máquinas app e coletor rodando
curl https://sc-mercados-api.fly.dev/v1/saude
```

Cada `fly deploy` seguinte aplica só as migrações novas (`migracao_aplicada`). Todas as tabelas têm RLS ligado sem
política: a API REST do Supabase, aberta com a chave pública, não lê nem grava nada (`db/testar.sql` confere).

## Dados de terceiros

Bairros e lojas das redes sem site: © colaboradores do OpenStreetMap, licença ODbL. A atribuição precisa aparecer na tela "Sobre" do app.

## Regras do projeto

- Toda regra de negócio tem teste com casos reais (preços da coleta de 22/10/2026).
- O coletor respeita robots.txt e no máximo 1 requisição por segundo, e nunca contorna bloqueios.
- Nenhum dado de CPF é guardado ou transmitido. Os cupons guardam só o hash da chave de acesso.
- Os agentes de IA só propõem; quem decide o que é publicado são as regras (`backend/src/quantofica/regras`).
