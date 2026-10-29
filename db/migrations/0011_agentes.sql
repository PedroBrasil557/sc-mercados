-- Agentes de bastidor. Por enquanto são programas de regras (sem IA), mas trabalham como um agente:
-- cada rodada fica registrada (o painel mostra se estão em dia) e cada decisão também, com confiança
-- e motivo, na tabela execucao_agente (modelo = 'regras-v1', custo zero).
create table agente_rodada (
  id            uuid primary key default gen_random_uuid(),
  agente        text not null,
  iniciada_em   timestamptz not null default now(),
  terminada_em  timestamptz,
  status        text not null default 'rodando' check (status in ('rodando', 'ok', 'falhou')),
  resumo        jsonb not null default '{}',
  erro          text
);
create index agente_rodada_agente on agente_rodada (agente, iniciada_em desc);
alter table agente_rodada enable row level security;

alter table execucao_agente drop constraint execucao_agente_agente_check;
alter table execucao_agente add constraint execucao_agente_agente_check
  check (agente in ('catalogador', 'leitor_encartes', 'casador_cupom', 'vigia', 'auditor', 'revisor', 'coletor'));
alter table execucao_agente add column rodada_id uuid references agente_rodada(id) on delete set null;
create index execucao_agente_entrada on execucao_agente (entrada_ref, criada_em desc);
