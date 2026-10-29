-- Produto que a rede não vende: a coleta não procura de novo por 7 dias (com o catálogo de ~700 itens,
-- procurar todos os ausentes todo dia levaria horas a 1 requisição por segundo).
create table ean_ausente (
  rede_id        uuid not null references rede(id),
  codigo         char(14) not null check (codigo ~ '^\d{14}$'),
  verificado_em  timestamptz not null default now(),
  primary key (rede_id, codigo)
);

alter table ean_ausente enable row level security;
