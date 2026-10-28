-- Identidade sem cadastro (R16): o aparelho recebe um token na primeira abertura. A conta (e-mail/Google)
-- é opcional e entra depois; até lá o token é quem identifica o membro da casa.

-- Só o SHA-256 do token fica no banco: um vazamento da tabela não dá acesso a nenhuma lista.
create table credencial (
  hash_token  char(64) primary key,
  membro_id   uuid not null references membro(id) on delete cascade,
  criada_em   timestamptz not null default now(),
  usada_em    timestamptz
);

create index credencial_membro on credencial (membro_id);

-- Quando o dono apaga a conta, a casa passa para quem entrou primeiro.
alter table membro add column entrou_em timestamptz not null default now();

-- Convite para entrar na casa: código curto que a família manda pelo WhatsApp. Vale 48 h e até 10 entradas.
create table convite (
  hash_codigo  char(64) primary key,
  casa_id      uuid not null references casa(id) on delete cascade,
  criado_por   uuid references membro(id) on delete set null,
  expira_em    timestamptz not null,
  usos         integer not null default 0 check (usos between 0 and 10)
);

-- Exclusão de conta (LGPD art. 18 e política da Google Play): apagar um membro anula a autoria das
-- operações dele (on delete set null), e isso é um UPDATE que o gatilho de imutabilidade barrava.
-- A API liga a exceção só dentro da transação de exclusão:  set local quantofica.exclusao_titular = 'sim'
create or replace function proibir_alteracao() returns trigger language plpgsql as $$
begin
  if tg_table_name = 'operacao_lista' and current_setting('quantofica.exclusao_titular', true) = 'sim' then
    return case when tg_op = 'DELETE' then old else new end;
  end if;
  raise exception '% é imutável: grave uma linha nova em vez de alterar ou apagar', tg_table_name;
end $$;
