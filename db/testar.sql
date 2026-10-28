-- Verificações do esquema. Rodar depois das migrações: cada bloco precisa terminar com "ok".
\set ON_ERROR_STOP on
begin;

insert into cidade (id, nome, uf) values ('00000000-0000-0000-0000-000000000001', 'Cidade de teste', 'SC');
insert into rede (id, nome, tem_api) values ('00000000-0000-0000-0000-000000000002', 'Rede de teste', true);
insert into loja (id, rede_id, cidade_id, nome) values ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'Giassi Victor Konder');
insert into categoria (id, nome, unidade_medida) values ('teste', 'Categoria de teste', 'g');
insert into produto (id, categoria_id, nome_humano, marca, tamanho, unidade) values ('00000000-0000-0000-0000-000000000004', 'teste', 'Produto de teste', 'Marca', 500, 'g');
insert into ean (codigo, produto_id) values ('07890000000017', '00000000-0000-0000-0000-000000000004');
insert into observacao_preco (id, produto_id, loja_id, preco_centavos, preco_de_centavos, fonte, observado_em)
  values ('00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000003', 2298, 2998, 'site', now());
select 'insercao: ok';

-- 1. observação de preço não pode ser alterada
do $$ begin
  update observacao_preco set preco_centavos = 1 where id = '00000000-0000-0000-0000-000000000005';
  raise exception 'FALHOU: update foi aceito';
exception when raise_exception then
  if sqlerrm like 'FALHOU%' then raise; end if;
end $$;
select 'observacao imutavel (update): ok';

-- 2. nem apagada
do $$ begin
  delete from observacao_preco where id = '00000000-0000-0000-0000-000000000005';
  raise exception 'FALHOU: delete foi aceito';
exception when raise_exception then
  if sqlerrm like 'FALHOU%' then raise; end if;
end $$;
select 'observacao imutavel (delete): ok';

-- 3. EAN precisa ter 14 dígitos
do $$ begin
  insert into ean (codigo, produto_id) values ('7896089013405', '00000000-0000-0000-0000-000000000004');
  raise exception 'FALHOU: EAN de 13 dígitos aceito';
exception when check_violation then null;
end $$;
select 'ean com 14 digitos: ok';

-- 4. preço em centavos positivos
do $$ begin
  insert into observacao_preco (produto_id, loja_id, preco_centavos, fonte, observado_em)
    values ('00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000003', 0, 'site', now());
  raise exception 'FALHOU: preço zero aceito';
exception when check_violation then null;
end $$;
select 'preco positivo: ok';

-- 5. economia nunca negativa (R12)
do $$ begin
  insert into cupom_lido (hash_chave, data_compra, total_centavos, economia_centavos)
    values (repeat('a', 64), current_date, 39840, -1);
  raise exception 'FALHOU: economia negativa aceita';
exception when check_violation then null;
end $$;
select 'economia nao negativa: ok';

-- 6. nenhuma coluna chamada cpf em todo o esquema (LGPD)
do $$ begin
  if exists (select 1 from information_schema.columns where table_schema = 'public' and column_name ilike '%cpf%') then
    raise exception 'FALHOU: existe coluna de CPF';
  end if;
end $$;
select 'sem coluna de cpf: ok';

-- 7. operação da lista é imutável no uso normal: apagar um membro (que anula a autoria) é barrado...
insert into casa (id) values ('00000000-0000-0000-0000-000000000006');
insert into membro (id, casa_id, apelido) values ('00000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000006', 'Ana');
insert into lista (id, casa_id, nome) values ('00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000006', 'Casa');
insert into operacao_lista (id, lista_id, item_id, membro_id, tipo, feita_em)
  values ('00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000007', gen_random_uuid(),
          '00000000-0000-0000-0000-000000000009', 'criar', now());
do $$ begin
  delete from membro where id = '00000000-0000-0000-0000-000000000009';
  raise exception 'FALHOU: membro apagado sem pedido de exclusão';
exception when raise_exception then
  if sqlerrm like 'FALHOU%' then raise; end if;
end $$;
select 'operacao imutavel fora da exclusao: ok';

-- 8. ...mas sai quando o titular pede a exclusão da conta (LGPD art. 18): a operação fica, sem autoria
set local quantofica.exclusao_titular = 'sim';
delete from membro where id = '00000000-0000-0000-0000-000000000009';
do $$ begin
  if (select membro_id from operacao_lista where id = '00000000-0000-0000-0000-000000000008') is not null then
    raise exception 'FALHOU: a operação continuou ligada ao membro apagado';
  end if;
end $$;
select 'exclusao do titular desliga a autoria: ok';

-- 9. toda tabela com RLS ligado: no Supabase, tabela sem RLS fica aberta na API REST com a chave pública
do $$
declare sem_rls text;
begin
  select string_agg(tablename, ', ') into sem_rls from pg_tables
   where schemaname = 'public' and not rowsecurity and tablename <> 'migracao_aplicada';
  if sem_rls is not null then
    raise exception 'FALHOU: tabelas sem RLS: % (crie a política na mesma migração)', sem_rls;
  end if;
end $$;
select 'todas as tabelas com rls: ok';

rollback;
