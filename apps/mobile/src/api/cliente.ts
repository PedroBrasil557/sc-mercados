/**
 * Cliente da API do SC Mercados.
 *
 * O token do aparelho fica no armazenamento seguro do sistema (Keystore no Android), nunca em texto puro.
 * Endereço da API: a do ar (Render) por padrão; para a API local, EXPO_PUBLIC_API_URL=http://<ip-do-pc>:8080.
 */
import * as SecureStore from "expo-secure-store";

import type { OperacaoDaLista } from "@/lista/regras";

const CHAVE_TOKEN = "quantofica.token";
export const API = process.env.EXPO_PUBLIC_API_URL ?? "https://sc-mercados-api.onrender.com";
/** Link do convite: abre a lista no navegador para quem ainda não tem o app (tela 14). */
export const linkDoConvite = (codigo: string) => `${API}/c/${codigo}`;
// O Render gratuito dorme sem uso e leva de 30 a 60 s para acordar na primeira chamada.
const TEMPO_LIMITE_MS = 75_000;

export class ErroDaApi extends Error {
  constructor(
    readonly status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

export const lerToken = () => SecureStore.getItemAsync(CHAVE_TOKEN);
const guardarToken = (token: string) => SecureStore.setItemAsync(CHAVE_TOKEN, token);
const esquecerToken = () => SecureStore.deleteItemAsync(CHAVE_TOKEN);

async function pedir<T>(metodo: string, caminho: string, corpo?: unknown, comToken = true): Promise<T> {
  const cabecalhos: Record<string, string> = { Accept: "application/json" };
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  if (comToken) {
    const token = await lerToken();
    if (!token) throw new ErroDaApi(401, "aparelho ainda não registrado");
    cabecalhos.Authorization = `Bearer ${token}`;
  }
  const controle = new AbortController();
  const relogio = setTimeout(() => controle.abort(), TEMPO_LIMITE_MS);
  try {
    const resp = await fetch(`${API}${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
      signal: controle.signal,
    });
    if (resp.status === 204) return undefined as T;
    const dados = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new ErroDaApi(resp.status, typeof dados?.detail === "string" ? dados.detail : `erro ${resp.status}`);
    return dados as T;
  } finally {
    clearTimeout(relogio);
  }
}

// ---------- Tipos (espelham backend/src/quantofica/api) ----------

export type Bairro = { id: string; nome: string; lat: number; lon: number };
export type Registro = { token: string; membro_id: string; casa_id: string; lista_id: string | null };
export type Eu = {
  membro: { id: string; apelido: string; papel: "dono" | "membro" };
  casa: { id: string; bairro_id: string | null; membros: { id: string; apelido: string; papel: string }[] };
  listas: { id: string; nome: string }[];
};
export type Operacao = OperacaoDaLista & { produto_id?: string | null; categoria_id?: string | null; qualquer_marca?: boolean };
export type Produto = {
  id: string;
  nome: string;
  marca: string | null;
  tamanho: string | null;
  unidade: string | null;
  categoria: string;
  nome_curto?: string | null;
  menor_preco_centavos?: number | null;
  menor_preco_rede?: string | null;
};
export type ItemDaLista = {
  id: string;
  quantidade: number;
  comprado: boolean;
  aviso: string | null;
  adicionado_por: string | null;
  produto_id: string | null;
  nome: string | null;
  nome_curto?: string | null;
  qualquer_marca?: boolean;
  marca: string | null;
  categoria: string | null;
  tamanho: string | null;
  unidade: string | null;
};
export type LojaComparada = {
  loja_id: string;
  rede: string;
  nome: string;
  bairro: string | null;
  distancia_km: number;
  custo_viagem_centavos: number;
  recomendada: boolean;
  nota: string | null; // "R$ 12,72 mais barato na prateleira, mas ... Não compensa."
  total_centavos: number;
  total_com_viagem_centavos?: number;
  seu_mercado?: boolean;
  /** Itens "qualquer marca": a marca mais barata desta loja (o que pegar na prateleira). */
  escolhas?: { item: string; produto_id: string; marca: string | null; nome: string | null }[];
  fora_da_soma: string[];
  comparacao_parcial: boolean;
  preco_mais_antigo_em: string | null;
  algum_preco_pode_ter_mudado: boolean;
};
/** Loja com poucos itens da lista (ex.: Fort, só o encarte): fica fora do total justo e aparece à parte. */
export type LojaComPoucosItens = {
  loja_id: string;
  rede: string;
  nome: string;
  bairro: string | null;
  distancia_km: number;
  itens: string[];
  total_centavos: number;
  mesmos_itens: number; // quantos destes a loja recomendada também vende
  mesmos_itens_aqui_centavos: number;
  mesmos_itens_na_recomendada_centavos: number;
  valido_ate: string | null; // validade do encarte
};
export type Comparacao = {
  comuns: number;
  itens: number;
  redes_sem_preco: { rede: string; distancia_km: number }[];
  lojas: LojaComparada[];
  lojas_com_poucos_itens?: LojaComPoucosItens[]; // opcional: comparação guardada antes desta versão
  divisao: null | {
    lojas: [string, string];
    total_centavos: number;
    economia_centavos: number;
    custo_deslocamento_centavos: number;
    distancia_extra_km: number;
    compensa: boolean;
  };
};

export type LojaPublica = { loja_id: string; rede: string; nome: string; bairro: string | null; distancia_km: number };
/** Tipo de preço que temos da loja: do site todo dia, só do encarte, ou ainda nenhum. */
export type TipoPreco = "site" | "encarte" | "sem";
export type Mercado = LojaPublica & { tipo_preco: TipoPreco };
export type Mercados = { seu_mercado: Mercado | null; automatico: boolean; lojas: Mercado[] };
export type ResultadoDaBusca = {
  produto_id: string;
  nome: string;
  nome_curto: string;
  marca: string | null;
  tamanho: string | null;
  unidade: string | null;
  tamanho_texto: string | null;
  categoria: string;
  grupo: string | null;
  preco_centavos: number | null;
  preco_por_unidade: string | null;
  desconto_pct: number;
  no_seu_mercado: boolean;
  onde: Mercado | null;
  mais_barato_longe: null | { rede: string; loja: string; distancia_km: number; preco_centavos: number };
};
export type GrupoQualquerMarca = {
  grupo: string;
  nome: string;
  produto_id: string;
  marcas: number;
  no_seu_mercado: boolean;
  a_partir_centavos: number;
  marca_mais_barata: string | null;
  em_oferta: boolean;
  categoria: string;
  tamanho_texto: string | null;
};
export type Faceta = { valor: string; n: number };
export type Busca = {
  termo: string;
  escondidos_zero: number;
  seu_mercado: Mercado | null;
  grupos: GrupoQualquerMarca[];
  total: number;
  produtos: ResultadoDaBusca[];
  filtros: { tipos: Faceta[]; tamanhos: Faceta[]; marcas: Faceta[]; redes: { rede: string; distancia_km: number; tipo_preco: TipoPreco }[] };
};
export type FiltrosDaBusca = {
  onde?: "seu" | "perto" | "todos";
  tipo?: string | null;
  tamanho?: string | null;
  marca?: string | null;
  rede?: string[];
  oferta?: boolean;
  mostrar_zero?: boolean;
  ordem?: "relevancia" | "preco" | "preco_unidade" | "desconto";
};
export type Inicio = {
  seu_mercado: Mercado | null;
  automatico: boolean;
  lista_id: string | null;
  acabando: { produto_id: string; nome_curto: string; tamanho_texto: string | null; vezes: number }[];
  encartes: { rede: string; loja: Mercado; valido_ate: string; itens: number }[];
  economia_mes_centavos: number;
  compras_no_mes: number;
  atividade: { quem: string | null; tipo: "criar" | "marcar" | "remover"; item: string; quando: string }[];
  status: { conferido_em: string | null; redes: number; produtos: number };
  basicos: { grupo: string; produto_id: string; nome: string }[];
};
export type PrecoNaLoja = LojaPublica & {
  preco_centavos: number;
  preco_de_centavos: number | null;
  fonte: string;
  observado_em: string;
  estado: "valido" | "pode_ter_mudado";
};
export type DetalheDoProduto = {
  produto: Produto & { ean: string | null; nome_curto?: string };
  precos: PrecoNaLoja[];
  historico: { dia: string; preco_centavos: number }[];
  seu_mercado?: (Mercado & { preco_centavos: number | null; preco_por_unidade?: string | null; observado_em?: string; fonte?: string }) | null;
  por_rede?: (LojaPublica & { preco_centavos: number | null; lojas_mesmo_preco?: number; motivo?: string })[];
  veredito?: null | { rede: string; loja: string; economia_centavos: number; viagem_centavos: number; km_ida_e_volta: number; compensa: boolean };
  equivalentes?: { produto_id: string; nome_curto: string; marca: string | null; tamanho: string | null; unidade: string | null; preco_centavos: number; economia_centavos: number | null }[];
  grupo?: string | null;
};
export type Oferta = LojaPublica & {
  produto: Produto;
  preco_centavos: number;
  referencia_centavos: number;
  desconto_pct: number;
  base: string;
  fonte?: string;
  valido_ate?: string | null;
  seu_mercado?: boolean;
  preco_por_unidade?: string | null;
  observado_em: string;
};
export type LojaDaRede = LojaPublica & { total_centavos: number; itens_com_preco: number; itens: number };
export type ItemDoCupom = { descricao: string; codigo: string; quantidade: number; valor_total_centavos: number };
export type CupomLido = {
  loja: string | null;
  total_centavos: number;
  itens: number;
  itens_reconhecidos: number;
  economia: null | { economia_centavos: number; pago_centavos: number; media_centavos: number; base: string };
};

// ---------- Rotas ----------

export const api = {
  bairros: () => pedir<Bairro[]>("GET", "/v1/bairros", undefined, false),

  async registrar(apelido: string, bairroId?: string): Promise<Registro> {
    const r = await pedir<Registro>("POST", "/v1/aparelhos", { apelido, bairro_id: bairroId }, false);
    await guardarToken(r.token);
    return r;
  },

  async entrarComConvite(codigo: string, apelido: string): Promise<Registro> {
    const r = await pedir<Registro>("POST", `/v1/convites/${encodeURIComponent(codigo)}`, { apelido }, false);
    await guardarToken(r.token);
    return r;
  },

  produtos: (busca = "") => pedir<Produto[]>("GET", `/v1/produtos?busca=${encodeURIComponent(busca)}&limite=200`),
  gerarRecuperacao: () => pedir<{ codigo: string }>("POST", "/v1/eu/recuperacao"),
  async recuperar(codigo: string): Promise<Registro> {
    const r = await pedir<Registro>("POST", "/v1/recuperar", { codigo }, false);
    await guardarToken(r.token);
    return r;
  },
  convidar: () => pedir<{ codigo: string; expira_em: string; usos_restantes: number }>("POST", "/v1/casa/convites"),
  eu: () => pedir<Eu>("GET", "/v1/eu"),
  alterarEu: (mudanca: { apelido?: string; bairro_id?: string }) => pedir<Eu>("PATCH", "/v1/eu", mudanca),

  async excluirConta(): Promise<void> {
    await pedir<void>("DELETE", "/v1/eu");
    await esquecerToken();
  },

  enviarOperacoes: (listaId: string, operacoes: Operacao[]) =>
    pedir<{ recebidas: number; novas: number; cursor: number }>("POST", `/v1/listas/${listaId}/operacoes`, { operacoes }),
  operacoesDesde: (listaId: string, cursor: number) =>
    pedir<{ operacoes: (Operacao & { seq: number })[]; cursor: number }>("GET", `/v1/listas/${listaId}/operacoes?desde=${cursor}`),
  lista: (listaId: string) => pedir<{ itens: ItemDaLista[]; cursor: number }>("GET", `/v1/listas/${listaId}`),
  produto: (id: string, custoKm = 90) => pedir<DetalheDoProduto>("GET", `/v1/produtos/${id}?custo_km=${custoKm}`),
  busca: (q: string, f: FiltrosDaBusca = {}) => {
    const p = new URLSearchParams({ q });
    for (const [k, v] of Object.entries(f)) {
      if (v === undefined || v === null || v === false) continue;
      if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
      else p.append(k, String(v));
    }
    return pedir<Busca>("GET", `/v1/busca?${p.toString()}`);
  },
  mercados: () => pedir<Mercados>("GET", "/v1/mercados"),
  escolherMercado: (lojaId: string | null) => pedir<Mercados>("PUT", "/v1/casa/mercado", { loja_id: lojaId }),
  inicio: () => pedir<Inicio>("GET", "/v1/inicio"),
  produtoPorEan: (codigo: string) => pedir<Produto>("GET", `/v1/produtos/ean/${encodeURIComponent(codigo)}`),
  outrasLojas: (rede: string, itens: Record<string, number>) =>
    pedir<{ rede: string; lojas: LojaDaRede[] }>("POST", "/v1/comparar/rede", { rede, itens }),
  ofertas: () => pedir<{ ofertas: Oferta[]; seu_mercado: Mercado | null }>("GET", "/v1/ofertas"),
  reportarPreco: (produtoId: string, lojaId: string, precoCentavos: number) =>
    pedir<{ id: string }>("POST", "/v1/reportes", { produto_id: produtoId, loja_id: lojaId, preco_centavos: precoCentavos }),
  lerCupom: (cupom: { chave: string; emitente: string | null; cnpj: string | null; emitido_em: string; total_centavos: number; itens: ItemDoCupom[] }) =>
    pedir<CupomLido>("POST", "/v1/cupons", cupom),
  economia: () => pedir<{ mes: string; economia_centavos: number; cupons: number }>("GET", "/v1/economia"),
  /** Itens = produto -> quantidade, como estão no aparelho (inclui mudanças ainda não enviadas). */
  comparar: (bairroId: string, itens: Record<string, number>, preferidas: string[] = [], custoKmCentavos = 90, qualquerMarca: string[] = []) =>
    pedir<Comparacao>("POST", "/v1/comparar", {
      bairro_id: bairroId,
      itens,
      preferidas,
      custo_km_centavos: custoKmCentavos,
      qualquer_marca: qualquerMarca,
    }),
  precosNaLoja: (lojaId: string, produtoIds: string[]) =>
    pedir<{ precos: Record<string, { preco_centavos: number; preco_de_centavos: number | null; fonte: string; observado_em: string }> }>(
      "GET",
      `/v1/precos?loja_id=${lojaId}${produtoIds.map((p) => `&produto_id=${p}`).join("")}`,
    ),
};
