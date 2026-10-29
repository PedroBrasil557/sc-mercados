/**
 * Números e datas como o app mostra. O espaço entre "R$" e o valor, e entre o número e a unidade,
 * é inseparável (NBSP): o preço nunca quebra em duas linhas.
 */
const NBSP = " ";
const MOEDA = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** 39840 → "R$ 398,40" */
export function reais(centavos: number): string {
  return `R$${NBSP}${MOEDA.format(centavos / 100)}`;
}

/** Diferença com sinal: 3074 → "+R$ 30,74"; −2055 → "−R$ 20,55" (sinal de menos tipográfico). */
export function diferenca(centavos: number): string {
  return `${centavos < 0 ? "−" : "+"}${reais(Math.abs(centavos))}`;
}

/** 0.84 → "0,8 km" */
export function km(valor: number): string {
  return `${valor.toLocaleString("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: valor < 10 ? 1 : 0 })}${NBSP}km`;
}

/** Tamanho do produto: 5000 g → "5 kg"; 900 ml → "900 ml"; 12 un → "12 un" */
export function tamanho(quantidade: number | string | null, unidade: string | null): string | null {
  if (quantidade === null || unidade === null) return null;
  const q = Number(quantidade);
  const numero = (v: number) => v.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  if (unidade === "g" && q >= 1000) return `${numero(q / 1000)}${NBSP}kg`;
  if (unidade === "ml" && q >= 1000) return `${numero(q / 1000)}${NBSP}L`;
  return `${numero(q)}${NBSP}${unidade}`;
}

/** Selo de fonte (R6): "SITE · HOJE 8H", "SITE · ONTEM 17H", "SITE · 22/10 19H35" */
export function seloDeFonte(fonte: string, quando: string | Date, agora = new Date()): string {
  const d = new Date(quando);
  const hora = d.getMinutes() ? `${d.getHours()}H${String(d.getMinutes()).padStart(2, "0")}` : `${d.getHours()}H`;
  const dia = (x: Date) => x.toDateString();
  const ontem = new Date(agora);
  ontem.setDate(agora.getDate() - 1);
  const quandoTexto =
    dia(d) === dia(agora) ? `HOJE ${hora}` : dia(d) === dia(ontem) ? `ONTEM ${hora}` : `${d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} ${hora}`;
  return `${fonte.toUpperCase()} · ${quandoTexto}`;
}

/** Quantidade na lista: 2 → "2"; 1.5 → "1,5" */
export function quantidade(valor: number): string {
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: 3 });
}
