/**
 * Regra R15 no aparelho: estado da lista a partir das operações de todos os aparelhos da casa.
 *
 * Espelho de backend/src/quantofica/regras/lista.py. Os dois são testados contra os mesmos casos
 * (compartilhado/r15_casos.json): se um mudar, o outro tem de mudar junto.
 * Arquivo puro, sem React Native: roda também nos testes do Node.
 */

export type TipoOperacao = "criar" | "somar" | "tirar" | "marcar" | "desmarcar" | "remover";

export type OperacaoDaLista = {
  id: string;
  item_id: string;
  tipo: TipoOperacao;
  feita_em: string; // ISO 8601 com fuso
  membro_id?: string | null;
  valor?: number | null;
};

export type EstadoDoItem = {
  id: string;
  quantidade: number;
  comprado: boolean;
  removido: boolean;
  removido_por: string | null;
  aviso: string | null; // "Paulo tinha removido este item"
  adicionado_por: string | null;
};

// Quantidades com até 3 casas (kg de banana), como o numeric(10, 3) do banco.
const arredondar = (v: number) => Math.round(v * 1000) / 1000;

function antes(a: OperacaoDaLista, b: OperacaoDaLista): number {
  const diferenca = Date.parse(a.feita_em) - Date.parse(b.feita_em);
  if (diferenca !== 0) return diferenca;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

/** Estado final de cada item. Itens removidos ficam no resultado com `removido: true`. */
export function aplicar(operacoes: OperacaoDaLista[], nomes: Record<string, string> = {}): Map<string, EstadoDoItem> {
  const itens = new Map<string, EstadoDoItem>();
  for (const op of [...operacoes].sort(antes)) {
    let it = itens.get(op.item_id);
    if (!it) {
      it = { id: op.item_id, quantidade: 0, comprado: false, removido: false, removido_por: null, aviso: null, adicionado_por: null };
      itens.set(op.item_id, it);
    }
    const membro = op.membro_id ?? null;
    const valor = op.valor ?? 1;
    switch (op.tipo) {
      case "criar":
      case "somar":
        if (it.removido && it.removido_por && it.removido_por !== membro) {
          it.aviso = `${nomes[it.removido_por] ?? "Alguém da casa"} tinha removido este item`;
        }
        if (it.removido) {
          it.quantidade = 0;
          it.removido = false;
          it.removido_por = null;
        }
        it.quantidade = arredondar(it.quantidade + valor);
        it.adicionado_por = it.adicionado_por ?? membro;
        break;
      case "tirar":
        it.quantidade = Math.max(0, arredondar(it.quantidade - valor));
        if (it.quantidade === 0) {
          it.removido = true;
          it.removido_por = membro;
        }
        break;
      case "remover":
        it.removido = true;
        it.removido_por = membro;
        it.aviso = null;
        break;
      case "marcar":
        it.comprado = true;
        break;
      case "desmarcar":
        it.comprado = false;
        break;
    }
  }
  return itens;
}
