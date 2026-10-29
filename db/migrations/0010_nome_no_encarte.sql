-- Item de encarte ligado a produto(s) no painel de revisão: no próximo encarte, o mesmo nome casa sozinho.
create table nome_no_encarte (
  rede_id     uuid not null references rede(id),
  nome        text not null,  -- normalizado: minúsculas, sem acento, palavras separadas por um espaço
  produto_id  uuid not null references produto(id),
  criado_em   timestamptz not null default now(),
  primary key (rede_id, nome, produto_id)
);

alter table nome_no_encarte enable row level security;
