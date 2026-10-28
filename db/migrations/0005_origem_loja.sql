-- De onde veio o cadastro da loja: da própria rede (endereço e coordenadas oficiais) ou do OpenStreetMap
-- (precisa ser confirmado no local). A mesma loja não pode aparecer duas vezes para o mesmo código da rede.
alter table loja add column origem text not null default 'rede' check (origem in ('rede', 'openstreetmap', 'manual'));
alter table loja add column confirmada_em timestamptz;
create unique index loja_seller on loja (rede_id, seller_id) where seller_id is not null;
