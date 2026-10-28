/**
 * R15 no app contra os casos compartilhados com o servidor, em todas as ordens de chegada.
 * Roda com o executor de testes do próprio Node:  npm test
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { aplicar, type OperacaoDaLista, type TipoOperacao } from "./regras.ts";

type Caso = {
  nome: string;
  nomes?: Record<string, string>;
  operacoes: { id: string; item: string; tipo: TipoOperacao; segundos: number; membro: string; valor?: number }[];
  esperado: Record<string, { quantidade: number; comprado: boolean; removido: boolean; aviso: string | null }>;
};

const arquivo = new URL("../../../../compartilhado/r15_casos.json", import.meta.url);
const casos: Caso[] = JSON.parse(readFileSync(arquivo, "utf-8")).casos;
const T0 = Date.parse("2026-10-28T12:00:00Z");

function* permutacoes<T>(lista: T[]): Generator<T[]> {
  if (lista.length <= 1) return yield lista;
  for (let i = 0; i < lista.length; i++) {
    for (const resto of permutacoes([...lista.slice(0, i), ...lista.slice(i + 1)])) yield [lista[i]!, ...resto];
  }
}

for (const caso of casos) {
  test(caso.nome, () => {
    const ops: OperacaoDaLista[] = caso.operacoes.map((o) => ({
      id: o.id,
      item_id: o.item,
      tipo: o.tipo,
      feita_em: new Date(T0 + o.segundos * 1000).toISOString(),
      membro_id: o.membro,
      valor: o.valor ?? null,
    }));
    for (const ordem of permutacoes(ops)) {
      const obtido = Object.fromEntries(
        [...aplicar(ordem, caso.nomes).values()].map((i) => [
          i.id,
          { quantidade: i.quantidade, comprado: i.comprado, removido: i.removido, aviso: i.aviso },
        ]),
      );
      assert.deepEqual(obtido, caso.esperado);
    }
  });
}
