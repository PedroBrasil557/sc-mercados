-- Quanto Fica: modelo de dados inicial (especificação, seção "Modelo de dados").
-- Valores em centavos (inteiros), datas em UTC (timestamptz), EAN sempre com 14 dígitos (R1).
-- Nenhuma tabela guarda CPF; o cupom guarda só o hash da chave de acesso (LGPD).

create extension if not exists pgcrypto;

-- ---------- Lugares ----------
create table cidade (
  id          uuid primary key default gen_random_uuid(),
  nome        text not null,
  uf          char(2) not null,
  unique (nome, uf)
);

create table bairro (
  id          uuid primary key default gen_random_uuid(),
  cidade_id   uuid not null references cidade(id),
  nome        text not null,
  lat_centro  double precision not null,
  lon_centro  double precision not null,
  unique (cidade_id, nome)
);

create table rede (
  id       uuid primary key default gen_random_uuid(),
  nome     text not null unique,
  site     text,
  tem_api  boolean not null default false
);

create table loja (
  id         uuid primary key default gen_random_uuid(),
  rede_id    uuid not null references rede(id),
  cidade_id  uuid not null references cidade(id),
  bairro_id  uuid references bairro(id),
  nome       text not null,
  cnpj       char(14) unique check (cnpj ~ '^\d{14}$'),
  endereco   text,
  lat        double precision,
  lon        double precision,
  seller_id  text,
  parceira   boolean not null default false
);

-- ---------- Catálogo ----------
create table categoria (
  id                 text primary key,  -- laticinios, cafe, graos...
  nome               text not null,
  atributos_chave    jsonb not null default '[]',
  unidade_medida     text not null check (unidade_medida in ('g', 'ml', 'un')),
  peso_medio_un_g    integer check (peso_medio_un_g > 0)
);

create table produto (
  id            uuid primary key default gen_random_uuid(),
  categoria_id  text not null references categoria(id),
  nome_humano   text not null,
  marca         text,
  tamanho       numeric(12, 3),
  unidade       text check (unidade in ('g', 'ml', 'un')),
  atributos     jsonb not null default '{}',
  foto_url      text,  -- só foto licenciada; nula = miniatura tipográfica
  criado_em     timestamptz not null default now()
);

create table ean (
  codigo      char(14) primary key check (codigo ~ '^\d{14}$'),
  produto_id  uuid not null references produto(id),
  status      text not null default 'ok' check (status in ('ok', 'em_revisao'))
);

create table produto_na_rede (
  id            uuid primary key default gen_random_uuid(),
  produto_id    uuid not null references produto(id),
  rede_id       uuid not null references rede(id),
  sku           text not null,
  nome_no_site  text,
  unique (rede_id, sku)
);

create table codigo_item_loja (
  cnpj_loja         char(14) not null check (cnpj_loja ~ '^\d{14}$'),
  codigo_interno    text not null,
  produto_id        uuid references produto(id),
  descricao_cupom   text not null,
  status            text not null default 'pendente' check (status in ('pendente', 'confirmado', 'recusado')),
  confirmado_por    text,
  primary key (cnpj_loja, codigo_interno)
);

-- ---------- Agentes e revisão ----------
create table execucao_agente (
  id              uuid primary key default gen_random_uuid(),
  agente          text not null check (agente in ('catalogador', 'leitor_encartes', 'casador_cupom', 'vigia', 'auditor')),
  versao_prompt   text not null,
  modelo          text not null,
  entrada_ref     text not null,
  saida           jsonb,
  confianca       numeric(4, 3) check (confianca between 0 and 1),
  validacoes      jsonb not null default '[]',
  decisao         text not null check (decisao in ('publicado', 'fila', 'descartado')),
  custo_tokens    integer check (custo_tokens >= 0),
  criada_em       timestamptz not null default now()
);

create table fila_revisao (
  id               uuid primary key default gen_random_uuid(),
  tipo             text not null check (tipo in ('ean', 'encarte', 'cupom', 'categoria', 'reporte', 'anomalia')),
  referencia_id    text not null,
  proposta_agente  jsonb,
  motivo           text not null,
  prioridade       smallint not null default 3 check (prioridade between 1 and 5),
  status           text not null default 'aberta' check (status in ('aberta', 'resolvida', 'descartada')),
  revisado_por     text,
  decidido_em      timestamptz,
  criada_em        timestamptz not null default now()
);

-- ---------- Preços (R5, R6) ----------
create table observacao_preco (
  id                   uuid primary key default gen_random_uuid(),
  produto_id           uuid not null references produto(id),
  loja_id              uuid not null references loja(id),
  preco_centavos       integer not null check (preco_centavos > 0),
  preco_de_centavos    integer check (preco_de_centavos > 0),
  faixa                text not null default 'varejo' check (faixa in ('varejo', 'atacado', 'clube', 'app')),
  qtd_minima           integer check (qtd_minima > 0),
  fonte                text not null check (fonte in ('site', 'encarte', 'cupom', 'etiqueta', 'feed_oficial')),
  observado_em         timestamptz not null,
  valido_ate           timestamptz,
  evidencia_id         text,
  execucao_agente_id   uuid references execucao_agente(id),
  criada_em            timestamptz not null default now()
);
create index observacao_preco_busca on observacao_preco (produto_id, loja_id, faixa, observado_em desc);

-- Observação de preço é imutável: cada leitura vira uma linha nova (modelo de dados).
create or replace function proibir_alteracao() returns trigger language plpgsql as $$
begin
  raise exception '% é imutável: grave uma linha nova em vez de alterar ou apagar', tg_table_name;
end $$;

create trigger observacao_preco_imutavel before update or delete on observacao_preco
  for each row execute function proibir_alteracao();

-- ---------- Casa e lista ----------
create table casa (
  id         uuid primary key default gen_random_uuid(),
  bairro_id  uuid references bairro(id),
  config     jsonb not null default '{}',  -- custo por km, lojas favoritas
  criada_em  timestamptz not null default now()
);

create table membro (
  id              uuid primary key default gen_random_uuid(),
  casa_id         uuid not null references casa(id) on delete cascade,
  apelido         text not null,
  dispositivo_id  text,
  conta_id        uuid,  -- opcional (R16)
  papel           text not null default 'membro' check (papel in ('dono', 'membro'))
);

create table lista (
  id       uuid primary key default gen_random_uuid(),
  casa_id  uuid not null references casa(id) on delete cascade,
  nome     text not null
);

create table item_lista (
  id                   uuid primary key default gen_random_uuid(),
  lista_id             uuid not null references lista(id) on delete cascade,
  produto_id           uuid references produto(id),
  categoria_id         text references categoria(id),
  atributos_desejados  jsonb not null default '{}',
  tamanho_desejado     numeric(12, 3),
  quantidade           numeric(10, 3) not null default 1 check (quantidade > 0),
  marca_fixa           text,
  comprado             boolean not null default false,
  adicionado_por       uuid references membro(id) on delete set null,
  atualizado_em        timestamptz not null default now(),
  check (produto_id is not null or categoria_id is not null)  -- item genérico usa a categoria (R3)
);

-- Sincronização por operações (R15): a quantidade final é a soma das operações, nunca "a última vence".
create table operacao_lista (
  id         uuid primary key,  -- gerado no aparelho, evita duplicidade ao reenviar
  lista_id   uuid not null references lista(id) on delete cascade,
  item_id    uuid not null,
  membro_id  uuid references membro(id) on delete set null,
  tipo       text not null check (tipo in ('criar', 'somar', 'tirar', 'marcar', 'desmarcar', 'remover')),
  valor      numeric(10, 3),
  feita_em   timestamptz not null
);
create index operacao_lista_ordem on operacao_lista (lista_id, feita_em);
create trigger operacao_lista_imutavel before update on operacao_lista
  for each row execute function proibir_alteracao();

-- Histórico de intenção de compra (B2): pseudônimo da casa, nunca dado pessoal.
create table evento_lista (
  id             bigserial primary key,
  casa_hash      text not null,
  produto_id     uuid references produto(id),
  categoria_id   text references categoria(id),
  tipo           text not null check (tipo in ('adicionado', 'removido', 'marca_trocada', 'loja_escolhida')),
  loja_id        uuid references loja(id),
  ocorrido_em    timestamptz not null
);
create trigger evento_lista_imutavel before update on evento_lista
  for each row execute function proibir_alteracao();

create table evento_uso (
  id             bigserial primary key,
  casa_id        uuid references casa(id) on delete cascade,
  membro_id      uuid references membro(id) on delete set null,
  nome_evento    text not null,
  propriedades   jsonb not null default '{}',
  versao_app     text not null,
  ocorrido_em    timestamptz not null
);

create table cupom_lido (
  id                 uuid primary key default gen_random_uuid(),
  casa_id            uuid references casa(id) on delete cascade,
  hash_chave         char(64) not null unique,  -- SHA-256 da chave de acesso; a chave completa nunca é guardada
  loja_id            uuid references loja(id),
  data_compra        date not null,
  total_centavos     integer not null check (total_centavos >= 0),
  economia_centavos  integer not null default 0 check (economia_centavos >= 0)  -- R12: nunca negativa
);

create table reporte_preco (
  id              uuid primary key default gen_random_uuid(),
  membro_id       uuid references membro(id) on delete set null,
  produto_id      uuid not null references produto(id),
  loja_id         uuid not null references loja(id),
  preco_centavos  integer not null check (preco_centavos > 0),
  foto_id         text,
  status          text not null default 'pendente' check (status in ('pendente', 'confirmado', 'recusado')),
  criado_em       timestamptz not null default now()
);
