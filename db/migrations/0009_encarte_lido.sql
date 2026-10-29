-- Encarte já lido: a coleta diária dos encartes pula o que já leu (cada encarte vale vários dias).
create table encarte_lido (
  rede_id     uuid not null references rede(id),
  encarte_id  text not null,
  titulo      text not null,
  valido_ate  date,
  itens       integer not null default 0,
  precos      integer not null default 0,  -- observações gravadas (produto x loja x faixa)
  lido_em     timestamptz not null default now(),
  primary key (rede_id, encarte_id)
);

alter table encarte_lido enable row level security;
