-- Mantém a API acordada (o plano grátis do Render dorme depois de 15 minutos sem acesso, e a primeira chamada
-- levava ~20 s). Roda só no Supabase de produção (pg_cron e pg_net não existem no Postgres de teste), por isso
-- não é uma migração. Aplicado em 04/11/2026. As 750 h/mês grátis do Render cobrem um serviço ligado o mês todo.
create extension if not exists pg_net;
create extension if not exists pg_cron with schema pg_catalog;
select cron.schedule('acordar-api', '*/5 * * * *',
  $$select net.http_get('https://sc-mercados-api.onrender.com/v1/saude', timeout_milliseconds := 60000)$$);
select cron.schedule('limpar-historico-cron', '0 4 * * *',
  $$delete from cron.job_run_details where end_time < now() - interval '3 days'$$);
