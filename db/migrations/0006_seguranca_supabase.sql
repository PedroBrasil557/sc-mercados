-- O Supabase publica as tabelas do schema public numa API REST própria, acessível com a chave "anon".
-- Ninguém do lado de fora pode ler ou gravar direto: só a nossa API, que conecta como dona das tabelas.
-- Liga RLS sem nenhuma política (nega tudo para os outros papéis) e tira os privilégios de anon/authenticated.
-- No Postgres local esses papéis não existem e o dono das tabelas ignora o RLS: nada muda.
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
  end loop;
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema public from anon, authenticated';
    execute 'revoke all on all sequences in schema public from anon, authenticated';
    execute 'revoke all on all functions in schema public from anon, authenticated';
    execute 'alter default privileges in schema public revoke all on tables from anon, authenticated';
    execute 'alter default privileges in schema public revoke all on sequences from anon, authenticated';
    execute 'alter default privileges in schema public revoke all on functions from anon, authenticated';
  end if;
end $$;
