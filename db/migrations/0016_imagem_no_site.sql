-- Endereço da foto do produto no site de cada rede. Só para teste no app (modo de desenvolvimento): a foto é da rede
-- ou do fabricante, e exibir no app publicado depende de autorização. A coluna produto.foto_url continua sendo a
-- única para foto licenciada.
alter table produto_na_rede add column imagem_url text;
