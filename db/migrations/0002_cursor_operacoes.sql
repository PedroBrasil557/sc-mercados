-- Cursor de sincronização (R15): o app pede "operações depois do número N".
-- O número cresce na ordem em que o servidor recebe, independente do relógio dos aparelhos.
alter table operacao_lista add column seq bigserial;
create unique index operacao_lista_seq on operacao_lista (lista_id, seq);
