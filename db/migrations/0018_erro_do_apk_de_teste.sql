-- O APK de teste (perfil preview do EAS, MODO_TESTE) manda os erros com ambiente "teste".
alter table erro_app drop constraint erro_app_ambiente_check;
alter table erro_app add constraint erro_app_ambiente_check check (ambiente in ('desenvolvimento', 'teste', 'publicado'));
