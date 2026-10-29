import assert from "node:assert/strict";
import { test } from "node:test";

import { centavos, converter, dataIso, enderecoDaConsulta, extrairChave } from "./nfce.ts";

const CHAVE = "42261012345678000199650010000012341000123456";

test("chave de acesso do QR (link com ?p=) e da chave digitada com espaços", () => {
  assert.equal(extrairChave(`https://sat.sef.sc.gov.br/nfce/consulta?p=${CHAVE}|2|1|1|ABCDEF0123`), CHAVE);
  assert.equal(extrairChave("4226 1012 3456 7800 0199 6500 1000 0012 3410 0012 3456"), CHAVE);
  assert.equal(extrairChave("https://exemplo.com/sem-chave"), null);
});

test("endereço da consulta", () => {
  const qr = `https://sat.sef.sc.gov.br/nfce/consulta?p=${CHAVE}|2|1|1|X`;
  assert.equal(enderecoDaConsulta(qr, CHAVE), qr);
  assert.equal(enderecoDaConsulta(CHAVE, CHAVE), `https://sat.sef.sc.gov.br/nfce/consulta?p=${CHAVE}`);
});

test("valores e datas no formato brasileiro", () => {
  assert.equal(centavos("1.234,56"), 123456);
  assert.equal(centavos("R$ 4,99"), 499);
  assert.equal(dataIso("Emissão: 28/10/2026 10:21:33"), "2026-10-28");
});

test("mensagem da página vira o cupom da API, sem nenhum dado do consumidor", () => {
  const mensagem = JSON.stringify({
    ok: true,
    emitente: "GIASSI & CIA LTDA",
    cnpj: "83.646.984/0001-02",
    emissao: "28/10/2026",
    total: "29,89",
    itens: [
      { descricao: "ARROZ KIARROZ T1 5KG", codigo: "7896084700119", quantidade: 1, valor: "22,90" },
      { descricao: "SAL CISNE 1KG", codigo: "4421", quantidade: 2, valor: "6,99" },
    ],
  });
  const cupom = converter(mensagem);
  assert.deepEqual(cupom, {
    emitente: "GIASSI & CIA LTDA",
    cnpj: "83646984000102",
    emitido_em: "2026-10-28",
    total_centavos: 2989,
    itens: [
      { descricao: "ARROZ KIARROZ T1 5KG", codigo: "7896084700119", quantidade: 1, valor_total_centavos: 2290 },
      { descricao: "SAL CISNE 1KG", codigo: "4421", quantidade: 2, valor_total_centavos: 699 },
    ],
  });
  assert.equal(converter(JSON.stringify({ ok: false })), null);
  assert.equal(converter("isso não é json"), null);
});
