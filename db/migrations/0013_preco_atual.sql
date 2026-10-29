-- Preço atual de cada produto em cada loja: uma linha por loja, produto, faixa e fonte, confirmada a cada coleta.
-- O histórico (observacao_preco) só ganha linha nova quando o preço muda: o banco cresce com as mudanças de
-- preço, não com os dias (com 10 mil produtos, uma linha por dia por loja encheria os 500 MB do plano grátis
-- do Supabase em semanas).
create table preco_atual (
  loja_id            uuid not null references loja(id),
  produto_id         uuid not null references produto(id),
  faixa              text not null,
  fonte              text not null,
  preco_centavos     integer not null check (preco_centavos > 0),
  preco_de_centavos  integer,
  observado_em       timestamptz not null,  -- última vez que o preço foi visto (a coleta confirma todo dia)
  desde              timestamptz not null,  -- desde quando o preço é este
  valido_ate         timestamptz,
  evidencia_id       text,
  primary key (loja_id, produto_id, faixa, fonte)
);
create index preco_atual_produto on preco_atual (produto_id);
alter table preco_atual enable row level security;

-- Toda observação nova, venha de onde vier (coleta, encarte, painel, cupom), atualiza o preço atual.
create or replace function atualizar_preco_atual() returns trigger language plpgsql as $$
begin
  insert into preco_atual (loja_id, produto_id, faixa, fonte, preco_centavos, preco_de_centavos, observado_em, desde,
                           valido_ate, evidencia_id)
  values (new.loja_id, new.produto_id, new.faixa, new.fonte, new.preco_centavos, new.preco_de_centavos, new.observado_em,
          new.observado_em, new.valido_ate, new.evidencia_id)
  on conflict (loja_id, produto_id, faixa, fonte) do update set
    preco_centavos = excluded.preco_centavos,
    preco_de_centavos = excluded.preco_de_centavos,
    observado_em = excluded.observado_em,
    valido_ate = excluded.valido_ate,
    evidencia_id = excluded.evidencia_id,
    desde = case when preco_atual.preco_centavos = excluded.preco_centavos then preco_atual.desde else excluded.observado_em end
  where excluded.observado_em >= preco_atual.observado_em;
  return new;
end $$;

create trigger observacao_atualiza_preco_atual after insert on observacao_preco
  for each row execute function atualizar_preco_atual();

-- O que já foi coletado: a observação mais recente de cada loja, produto, faixa e fonte vira o preço atual.
insert into preco_atual (loja_id, produto_id, faixa, fonte, preco_centavos, preco_de_centavos, observado_em, desde,
                         valido_ate, evidencia_id)
select distinct on (loja_id, produto_id, faixa, fonte)
       loja_id, produto_id, faixa, fonte, preco_centavos, preco_de_centavos, observado_em, observado_em, valido_ate, evidencia_id
from observacao_preco
order by loja_id, produto_id, faixa, fonte, observado_em desc
on conflict do nothing;
