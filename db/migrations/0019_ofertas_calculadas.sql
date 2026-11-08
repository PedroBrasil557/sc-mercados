-- Ofertas reais (R9) calculadas depois de cada coleta, para a tela de ofertas não refazer a conta a cada abertura
-- (eram 12 a 26 s no servidor grátis). Uma linha por loja e produto em oferta; a rodada diz se a conta é recente.
create table oferta_calculada (
  loja_id              uuid not null references loja(id) on delete cascade,
  produto_id           uuid not null references produto(id) on delete cascade,
  preco_centavos       integer not null,
  referencia_centavos  integer not null,
  desconto_pct         integer not null,
  base                 text not null,
  fonte                text not null,
  valido_ate           timestamptz,
  observado_em         timestamptz not null,
  calculado_em         timestamptz not null,
  primary key (loja_id, produto_id)
);

create table oferta_calculada_rodada (
  calculada_em  timestamptz primary key,
  ofertas       integer not null
);

alter table oferta_calculada enable row level security;
alter table oferta_calculada_rodada enable row level security;
