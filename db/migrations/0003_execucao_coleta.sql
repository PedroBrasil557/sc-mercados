-- Cada rodada do coletor por rede. O monitor de qualidade usa para saber se o coletor parou
-- e se a cobertura caiu de um dia para o outro.
create table execucao_coleta (
  id                uuid primary key default gen_random_uuid(),
  rede_id           uuid not null references rede(id),
  iniciada_em       timestamptz not null,
  terminada_em      timestamptz,
  eans_pedidos      integer not null default 0 check (eans_pedidos >= 0),
  precos_gravados   integer not null default 0 check (precos_gravados >= 0),
  enviados_revisao  integer not null default 0 check (enviados_revisao >= 0),
  status            text not null default 'rodando' check (status in ('rodando', 'ok', 'falhou')),
  erro              text
);

create index execucao_coleta_rede on execucao_coleta (rede_id, iniciada_em desc);
create index observacao_preco_produto_loja on observacao_preco (produto_id, loja_id, observado_em desc);
