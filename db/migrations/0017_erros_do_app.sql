-- Erros do app (monitoramento próprio, sem serviço de terceiros). Nada de dado pessoal: nem casa, nem membro, nem
-- token, nem IP. Erros iguais (mesma mensagem e lugar, mesma versão) viram uma linha com contagem.
create table erro_app (
  id           uuid primary key default gen_random_uuid(),
  assinatura   text not null,         -- sha-256 da mensagem + lugar: agrupa o mesmo erro
  mensagem     text not null,
  pilha        text,
  onde         text not null,         -- tela ou "global"
  versao       text not null,
  plataforma   text not null,
  ambiente     text not null check (ambiente in ('desenvolvimento', 'publicado')),
  fatal        boolean not null default false,
  vezes        integer not null default 1,
  primeira_em  timestamptz not null default now(),
  ultima_em    timestamptz not null default now(),
  unique (assinatura, versao, ambiente)
);
create index erro_app_ultima on erro_app (ultima_em desc);
alter table erro_app enable row level security;
