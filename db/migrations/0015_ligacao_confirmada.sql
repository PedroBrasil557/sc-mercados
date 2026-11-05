-- Ligação por nome (site do Fort, sem código de barras) confirmada pelo Revisor ou por uma pessoa: a trava de preço
-- contra os outros mercados (que existe para pegar ligação errada) deixa de valer para ela.
alter table produto_na_rede add column confirmada_em timestamptz;
