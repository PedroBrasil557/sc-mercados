/**
 * Sincronia da lista da casa (R15), pensada para funcionar sem internet.
 *
 * 1. Cada toque vira uma operação gravada no aparelho e aparece na tela na hora.
 * 2. Logo depois (e a cada 20 s, e quando o app volta para a frente) as pendentes vão para a API
 *    e voltam as operações dos outros aparelhos, a partir do último cursor.
 * 3. O estado é sempre recalculado de TODAS as operações com a mesma regra do servidor (regras.ts).
 */
import { randomUUID } from "expo-crypto";
import { useEffect, useSyncExternalStore } from "react";
import { AppState } from "react-native";

import { api, ErroDaApi, type Operacao, type Produto } from "@/api/cliente";

import * as armazem from "./armazem";
import { aplicar, type TipoOperacao } from "./regras";

export type ItemVisivel = {
  id: string;
  produto_id: string | null;
  nome: string;
  tamanho: string | null;
  unidade: string | null;
  marca: string | null;
  categoria: string | null;
  quantidade: number;
  comprado: boolean;
  aviso: string | null;
  adicionado_por: string | null;
};

export type Situacao = {
  pendentes: number;
  sincronizando: boolean;
  semConexao: boolean;
  erro: string | null;
  ultimaSincronia: number | null;
};

export type Instantaneo = { sessao: armazem.Sessao | null; itens: ItemVisivel[]; situacao: Situacao };

const LOTE = 500;
const INTERVALO_MS = 20_000;
const ESPERA_ENVIO_MS = 800;

let situacao: Situacao = { pendentes: 0, sincronizando: false, semConexao: false, erro: null, ultimaSincronia: null };
let instantaneo: Instantaneo | null = null;
const ouvintes = new Set<() => void>();

function calcular(): Instantaneo {
  const sessao = armazem.lerSessao();
  if (!sessao) return { sessao: null, itens: [], situacao };
  const infos = armazem.infos(sessao.lista_id);
  const itens: ItemVisivel[] = [];
  for (const it of aplicar(armazem.todas(sessao.lista_id), sessao.nomes).values()) {
    if (it.removido) continue;
    const info = infos.get(it.id);
    itens.push({
      id: it.id,
      produto_id: info?.produto_id ?? null,
      nome: info?.nome ?? "Item da casa",
      tamanho: info?.tamanho ?? null,
      unidade: info?.unidade ?? null,
      marca: info?.marca ?? null,
      categoria: info?.categoria ?? null,
      quantidade: it.quantidade,
      comprado: it.comprado,
      aviso: it.aviso,
      adicionado_por: it.adicionado_por ? (sessao.nomes[it.adicionado_por] ?? null) : null,
    });
  }
  // O que falta comprar primeiro; dentro de cada grupo, pela categoria e pelo nome.
  itens.sort((a, b) => Number(a.comprado) - Number(b.comprado) || (a.categoria ?? "").localeCompare(b.categoria ?? "") || a.nome.localeCompare(b.nome));
  situacao = { ...situacao, pendentes: armazem.pendentes(sessao.lista_id).length };
  return { sessao, itens, situacao };
}

function avisar(): void {
  instantaneo = calcular();
  ouvintes.forEach((f) => f());
}

function mudarSituacao(parcial: Partial<Situacao>): void {
  situacao = { ...situacao, ...parcial };
  avisar();
}

// ---------- O que a tela usa ----------

export function useLista(): Instantaneo {
  return useSyncExternalStore(
    (f) => {
      ouvintes.add(f);
      return () => ouvintes.delete(f);
    },
    () => (instantaneo ??= calcular()),
  );
}

/** Liga a sincronia automática enquanto o app está aberto. Usar uma vez, no layout raiz. */
export function useSincroniaAutomatica(): void {
  useEffect(() => {
    void sincronizar();
    const relogio = setInterval(() => AppState.currentState === "active" && void sincronizar(), INTERVALO_MS);
    const assinatura = AppState.addEventListener("change", (estado) => estado === "active" && void sincronizar());
    return () => {
      clearInterval(relogio);
      assinatura.remove();
    };
  }, []);
}

// ---------- Mudanças na lista ----------

let envioAgendado: ReturnType<typeof setTimeout> | null = null;

function fazer(itemId: string, tipo: TipoOperacao, extra: { valor?: number; produto?: Produto } = {}): void {
  const sessao = armazem.lerSessao();
  if (!sessao) throw new Error("aparelho ainda não registrado");
  const op: Operacao = {
    id: randomUUID(),
    item_id: itemId,
    tipo,
    feita_em: new Date().toISOString(),
    membro_id: sessao.membro_id,
    valor: extra.valor,
    produto_id: extra.produto?.id,
  };
  armazem.gravarLocal(sessao.lista_id, op);
  if (extra.produto) {
    const p = extra.produto;
    armazem.gravarInfo(sessao.lista_id, [
      { item_id: itemId, produto_id: p.id, nome: p.nome, marca: p.marca, categoria: p.categoria, tamanho: p.tamanho, unidade: p.unidade },
    ]);
  }
  avisar();
  if (envioAgendado) clearTimeout(envioAgendado);
  envioAgendado = setTimeout(() => void sincronizar(), ESPERA_ENVIO_MS);
}

/** Pôr um produto na lista: se ele já está (ou esteve), soma 1 no mesmo item; senão cria. */
export function adicionarProduto(produto: Produto): void {
  const sessao = armazem.lerSessao();
  if (!sessao) return;
  const existente = [...armazem.infos(sessao.lista_id).values()].find((i) => i.produto_id === produto.id);
  if (existente) fazer(existente.item_id, "somar", { produto });
  else fazer(randomUUID(), "criar", { produto });
}

export const somar = (itemId: string) => fazer(itemId, "somar");
export const tirar = (itemId: string) => fazer(itemId, "tirar");
export const remover = (itemId: string) => fazer(itemId, "remover");
/** Desfazer a remoção: o item volta com a quantidade que tinha. */
export const restaurar = (itemId: string, quantidade: number) => fazer(itemId, "somar", { valor: quantidade });
export const alternarComprado = (item: ItemVisivel) => fazer(item.id, item.comprado ? "desmarcar" : "marcar");

// ---------- Ida e volta com o servidor ----------

let emAndamento: Promise<void> | null = null;

export function sincronizar(): Promise<void> {
  emAndamento ??= executarSincronia().finally(() => {
    emAndamento = null;
  });
  return emAndamento;
}

async function executarSincronia(): Promise<void> {
  const sessao = armazem.lerSessao();
  if (!sessao) return;
  const lista = sessao.lista_id;
  mudarSituacao({ sincronizando: true });
  try {
    const pendentes = armazem.pendentes(lista);
    for (let i = 0; i < pendentes.length; i += LOTE) {
      const lote = pendentes.slice(i, i + LOTE);
      await api.enviarOperacoes(lista, lote);
      armazem.marcarEnviadas(lote.map((o) => o.id));
    }
    let cursor = armazem.cursor(lista);
    for (;;) {
      const r = await api.operacoesDesde(lista, cursor);
      armazem.gravarRecebidas(lista, r.operacoes, r.cursor);
      cursor = r.cursor;
      if (r.operacoes.length < LOTE) break;
    }
    // Itens que alguém da casa criou em outro aparelho: busca nome e marca uma vez.
    const conhecidos = armazem.infos(lista);
    const todas = armazem.todas(lista);
    if (todas.some((o) => !conhecidos.has(o.item_id))) {
      const atual = await api.lista(lista);
      armazem.gravarInfo(
        lista,
        atual.itens.map((i) => ({
          item_id: i.id,
          produto_id: i.produto_id,
          nome: i.nome,
          marca: i.marca,
          categoria: i.categoria,
          tamanho: i.tamanho,
          unidade: i.unidade,
        })),
      );
    }
    // Alguém novo na casa: atualiza os apelidos (avisos como "Paulo tinha removido este item").
    if (todas.some((o) => o.membro_id && !(o.membro_id in sessao.nomes))) {
      const eu = await api.eu();
      armazem.gravarSessao({ ...sessao, nomes: Object.fromEntries(eu.casa.membros.map((m) => [m.id, m.apelido])) });
    }
    mudarSituacao({ sincronizando: false, semConexao: false, erro: null, ultimaSincronia: Date.now() });
  } catch (e) {
    // Erro da API (ex.: 401) é problema de verdade; qualquer outro é falta de conexão: as mudanças ficam guardadas.
    if (e instanceof ErroDaApi) mudarSituacao({ sincronizando: false, erro: e.message });
    else mudarSituacao({ sincronizando: false, semConexao: true });
  }
}

// ---------- Entrar na casa ----------

type Bairro = { id: string; nome: string };

async function comecarSessao(
  r: { membro_id: string; casa_id: string; lista_id: string | null },
  apelido: string,
  bairro: Bairro | null,
): Promise<void> {
  if (!r.lista_id) throw new Error("a casa ainda não tem lista");
  armazem.gravarSessao({
    membro_id: r.membro_id,
    casa_id: r.casa_id,
    lista_id: r.lista_id,
    apelido,
    nomes: { [r.membro_id]: apelido },
    bairro_id: bairro?.id ?? null,
    bairro_nome: bairro?.nome ?? null,
  });
  avisar();
  await Promise.all([sincronizar(), buscarProdutos("")]);
}

/** Primeira abertura: a casa nasce com o bairro escolhido. O apelido pode ser trocado depois no Perfil. */
export async function comecarCasa(bairro: Bairro, apelido = "Eu"): Promise<void> {
  await comecarSessao(await api.registrar(apelido, bairro.id), apelido, bairro);
}

export async function entrarComConvite(codigo: string, apelido: string): Promise<void> {
  const r = await api.entrarComConvite(codigo.trim(), apelido.trim());
  await comecarSessao(r, apelido.trim(), null);
  // O bairro é o da casa em que entrou.
  const eu = await api.eu();
  const sessao = armazem.lerSessao();
  if (sessao && eu.casa.bairro_id) {
    const nome = (await api.bairros()).find((b) => b.id === eu.casa.bairro_id)?.nome ?? null;
    armazem.gravarSessao({ ...sessao, bairro_id: eu.casa.bairro_id, bairro_nome: nome });
    avisar();
  }
}

export async function trocarBairro(bairro: Bairro): Promise<void> {
  await api.alterarEu({ bairro_id: bairro.id });
  const sessao = armazem.lerSessao();
  if (sessao) armazem.gravarSessao({ ...sessao, bairro_id: bairro.id, bairro_nome: bairro.nome });
  avisar();
}

export async function trocarApelido(apelido: string): Promise<void> {
  const novo = apelido.trim();
  await api.alterarEu({ apelido: novo });
  const sessao = armazem.lerSessao();
  if (sessao) armazem.gravarSessao({ ...sessao, apelido: novo, nomes: { ...sessao.nomes, [sessao.membro_id]: novo } });
  avisar();
}

export async function apagarMinhaConta(): Promise<void> {
  await api.excluirConta();
  armazem.apagarTudo();
  avisar();
}

/** Busca no catálogo da API; sem internet, no catálogo guardado no aparelho. */
export async function buscarProdutos(busca: string): Promise<{ produtos: Produto[]; semConexao: boolean }> {
  try {
    const produtos = await api.produtos(busca);
    armazem.guardarCatalogo(produtos);
    return { produtos, semConexao: false };
  } catch {
    return { produtos: armazem.buscarNoCatalogo(busca), semConexao: true };
  }
}
