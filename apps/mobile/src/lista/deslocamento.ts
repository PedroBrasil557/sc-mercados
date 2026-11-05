/**
 * Como a casa vai ao mercado. Só muda a SUGESTÃO de mercado: os valores na tela são sempre os do caixa, e quem
 * decide aonde ir é a pessoa. A mesma tabela do servidor (backend/src/quantofica/regras/deslocamento.py).
 */
export type ModoDeViagem = "carro" | "moto" | "aplicativo" | "taxi" | "onibus" | "a_pe";

export const MODOS_DE_VIAGEM: { id: ModoDeViagem; nome: string; detalhe: string }[] = [
  { id: "carro", nome: "Carro", detalhe: "Combustível e desgaste, cerca de R$ 0,90 por km" },
  { id: "moto", nome: "Moto", detalhe: "Cerca de R$ 0,40 por km" },
  { id: "aplicativo", nome: "Uber ou 99", detalhe: "Corrida de ida e de volta (estimativa; o preço real é o do aplicativo)" },
  { id: "taxi", nome: "Táxi", detalhe: "Bandeirada e km pela tabela de Blumenau, ida e volta" },
  { id: "onibus", nome: "Ônibus", detalhe: "Duas passagens, iguais para qualquer mercado" },
  { id: "a_pe", nome: "A pé ou de bicicleta", detalhe: "A distância não pesa na sugestão" },
];

const FATOR_RUA = 1.3;
const A_PE_ATE_KM = 1;
const POR_KM: Partial<Record<ModoDeViagem, number>> = { carro: 90, moto: 40 };
const CORRIDAS: Partial<Record<ModoDeViagem, { base: number; km: number; minimo: number }>> = {
  aplicativo: { base: 250, km: 180, minimo: 750 },
  taxi: { base: 535, km: 436, minimo: 0 },
};
const PASSAGEM_ONIBUS = 550;

/** Custo de uma ida, em centavos (só para a sugestão; nunca aparece somado ao preço). */
export function perna(modo: ModoDeViagem, km: number): number {
  const d = Math.max(0, km);
  const porKm = POR_KM[modo];
  if (porKm !== undefined) return Math.round(d * porKm);
  const c = CORRIDAS[modo];
  if (c) return Math.max(c.minimo, Math.round(c.base + c.km * d * FATOR_RUA));
  if (modo === "onibus") return d <= A_PE_ATE_KM ? 0 : PASSAGEM_ONIBUS;
  return 0;
}

export const idaEVolta = (modo: ModoDeViagem, km: number) => 2 * perna(modo, km);
