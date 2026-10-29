import assert from "node:assert/strict";
import { test } from "node:test";

import { diferenca, km, reais, seloDeFonte, tamanho } from "./formatar.ts";

const NBSP = " ";

test("dinheiro em reais, com espaço que não quebra", () => {
  assert.equal(reais(39840), `R$${NBSP}398,40`);
  assert.equal(reais(123456), `R$${NBSP}1.234,56`);
  assert.equal(diferenca(3074), `+R$${NBSP}30,74`);
  assert.equal(diferenca(-2055), `−R$${NBSP}20,55`);
});

test("distância e tamanho", () => {
  assert.equal(km(0.84), `0,8${NBSP}km`);
  assert.equal(km(12.3), `12,3${NBSP}km`);
  assert.equal(tamanho(5000, "g"), `5${NBSP}kg`);
  assert.equal(tamanho("900.000", "ml"), `900${NBSP}ml`);
  assert.equal(tamanho(1500, "ml"), `1,5${NBSP}L`);
  assert.equal(tamanho(41.5, "g"), `41,5${NBSP}g`);
  assert.equal(tamanho(null, "g"), null);
});

test("selo de fonte com hoje, ontem e data", () => {
  const agora = new Date(2026, 9, 28, 15, 0);
  assert.equal(seloDeFonte("site", new Date(2026, 9, 28, 8, 0), agora), "SITE · HOJE 8H");
  assert.equal(seloDeFonte("site", new Date(2026, 9, 27, 17, 5), agora), "SITE · ONTEM 17H05");
  assert.equal(seloDeFonte("site", new Date(2026, 9, 22, 19, 35), agora), "SITE · 22/10 19H35");
});
