/**
 * Quanto fica a lista em cada mercado (telas Início e Comparar).
 *
 * Compara a lista como ela está NO APARELHO (inclui mudanças ainda não enviadas), no bairro da casa.
 * O último resultado fica guardado: sem internet, a tela mostra ele com o horário de quando foi calculado.
 */
import { useEffect, useMemo, useSyncExternalStore } from "react";

import { api, ErroDaApi, type Comparacao } from "@/api/cliente";

import { useMercados } from "./mercado";
import * as armazem from "./armazem";
import { useLista } from "./sincronia";

export type EstadoDaComparacao = {
  dados: Comparacao | null;
  calculadaEm: number | null;
  carregando: boolean;
  semConexao: boolean;
  erro: string | null;
};

const CHAVE = "comparacao";
const CHAVE_PREFERIDAS = "lojas_preferidas"; // rede -> loja escolhida pela casa (tela "Outras lojas da rede")

export function lojasPreferidas(): Record<string, string> {
  return armazem.lerGuardado<Record<string, string>>(CHAVE_PREFERIDAS) ?? {};
}

/** Quanto custa cada km de ida e volta para a casa (R8): carro, moto ou não contar (a pé, ônibus, já passa perto). */
export const OPCOES_DE_VIAGEM = [
  { centavos: 90, nome: "Carro", detalhe: "cerca de R$ 0,90 por km, ida e volta" },
  { centavos: 40, nome: "Moto", detalhe: "cerca de R$ 0,40 por km, ida e volta" },
  { centavos: 0, nome: "Não contar", detalhe: "a pé, de ônibus ou quando já passo perto" },
] as const;

export function custoKm(): number {
  return armazem.lerGuardado<number>("custo_km") ?? 90;
}

export function definirCustoKm(centavos: number): void {
  armazem.guardar("custo_km", centavos);
  ultimaChave = "";
  ouvintes.forEach((f) => f());
}

/** A casa escolhe a loja de uma rede; a comparação passa a usar ela no lugar da mais perto. */
export function escolherLoja(rede: string, lojaId: string): void {
  armazem.guardar(CHAVE_PREFERIDAS, { ...lojasPreferidas(), [rede]: lojaId });
  ultimaChave = "";
  ouvintes.forEach((f) => f());
}

let estado: EstadoDaComparacao = { dados: null, calculadaEm: null, carregando: false, semConexao: false, erro: null, ...lerGuardada() };
const ouvintes = new Set<() => void>();
let ultimaChave = "";
let pedido = 0;

function lerGuardada(): Partial<EstadoDaComparacao> {
  const g = armazem.lerGuardado<{ chave: string; dados: Comparacao; calculadaEm: number }>(CHAVE);
  if (!g) return {};
  ultimaChave = g.chave;
  return { dados: g.dados, calculadaEm: g.calculadaEm };
}

function mudar(parcial: Partial<EstadoDaComparacao>): void {
  estado = { ...estado, ...parcial };
  ouvintes.forEach((f) => f());
}

async function calcular(chave: string, bairroId: string, itens: Record<string, number>, genericos: string[], forcar: boolean): Promise<void> {
  if (!forcar && chave === ultimaChave && estado.dados) return;
  const meu = ++pedido;
  mudar({ carregando: true });
  try {
    const dados = Object.keys(itens).length ? await api.comparar(bairroId, itens, Object.values(lojasPreferidas()), custoKm(), genericos) : null;
    if (meu !== pedido) return; // chegou uma resposta mais nova
    ultimaChave = chave;
    const calculadaEm = Date.now();
    if (dados) armazem.guardar(CHAVE, { chave, dados, calculadaEm });
    mudar({ dados, calculadaEm, carregando: false, semConexao: false, erro: null });
  } catch (e) {
    if (meu !== pedido) return;
    if (e instanceof ErroDaApi) mudar({ carregando: false, erro: e.message });
    else mudar({ carregando: false, semConexao: true });
  }
}

/** Comparação da lista atual. Recalcula quando a lista ou o bairro mudam (com um pequeno atraso). */
export function useComparacao(): EstadoDaComparacao & { atualizar: () => void } {
  const { sessao, itens } = useLista();
  const atual = useSyncExternalStore(
    (f) => {
      ouvintes.add(f);
      return () => ouvintes.delete(f);
    },
    () => estado,
  );
  // Só o que falta comprar entra na conta; item genérico (sem produto) não tem preço.
  const quantidades = useMemo(() => {
    const q: Record<string, number> = {};
    for (const i of itens) if (i.produto_id && !i.comprado) q[i.produto_id] = (q[i.produto_id] ?? 0) + i.quantidade;
    return q;
  }, [itens]);
  const genericos = useMemo(
    () => [...new Set(itens.filter((i) => i.produto_id && i.qualquer_marca && !i.comprado).map((i) => i.produto_id as string))].sort(),
    [itens],
  );
  const mercados = useMercados(); // trocar o seu mercado refaz a conta
  const bairroId = sessao?.bairro_id ?? null;
  const chave = bairroId
    ? `${bairroId}|${mercados?.seu_mercado?.loja_id ?? ""}|${JSON.stringify(Object.entries(quantidades).sort())}|${genericos.join(",")}|${JSON.stringify(lojasPreferidas())}|${custoKm()}`
    : "";

  useEffect(() => {
    if (!bairroId) return;
    const espera = setTimeout(() => void calcular(chave, bairroId, quantidades, genericos, false), 500);
    return () => clearTimeout(espera);
  }, [chave, bairroId, quantidades, genericos]);

  return { ...atual, atualizar: () => bairroId && void calcular(chave, bairroId, quantidades, genericos, true) };
}
