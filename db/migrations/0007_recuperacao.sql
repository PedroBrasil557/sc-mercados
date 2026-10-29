-- "Não perca a sua lista" (R16, tela 20): código de recuperação para usar a mesma conta num celular novo.
-- Só o SHA-256 do código fica no banco. Sem e-mail, sem telefone, sem CPF.
alter table membro add column hash_recuperacao char(64) unique;
