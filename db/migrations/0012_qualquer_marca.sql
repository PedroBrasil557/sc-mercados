-- Item "qualquer marca": a lista guarda um produto de referência, mas cada mercado entra com o equivalente
-- mais barato do mesmo grupo (tipo + características + tamanho; ver regras/nome.py).
alter table item_lista add column qualquer_marca boolean not null default false;
