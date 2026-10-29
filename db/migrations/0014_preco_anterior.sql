-- Preço anterior no preço atual: "mudou de preço" deixa de ser "apareceu pela primeira vez". Com o Catalogador v2
-- (milhares de produtos novos de uma vez) o primeiro preço visto não pode virar candidato a oferta.
alter table preco_atual add column anterior_centavos integer;

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
    desde = case when preco_atual.preco_centavos = excluded.preco_centavos then preco_atual.desde else excluded.observado_em end,
    anterior_centavos = case when preco_atual.preco_centavos = excluded.preco_centavos then preco_atual.anterior_centavos
                             else preco_atual.preco_centavos end
  where excluded.observado_em >= preco_atual.observado_em;
  return new;
end $$;

-- O que já tem histórico: o último preço diferente antes do atual.
update preco_atual a set anterior_centavos = (
  select o.preco_centavos from observacao_preco o
  where o.loja_id = a.loja_id and o.produto_id = a.produto_id and o.faixa = a.faixa and o.fonte = a.fonte
    and o.observado_em < a.desde and o.preco_centavos <> a.preco_centavos
  order by o.observado_em desc limit 1
);
