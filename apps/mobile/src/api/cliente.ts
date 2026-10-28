/**
 * Cliente da API do Quanto Fica.
 *
 * O token do aparelho fica no armazenamento seguro do sistema (Keystore no Android), nunca em texto puro.
 * Endereço da API: variável EXPO_PUBLIC_API_URL (ex.: http://10.0.2.2:8000 no emulador Android).
 */
import * as SecureStore from "expo-secure-store";

const CHAVE_TOKEN = "quantofica.token";
const API = process.env.EXPO_PUBLIC_API_URL ?? "http://10.0.2.2:8000";
const TEMPO_LIMITE_MS = 15_000;

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

export type Bairro = { id: string; nome: string };
export type Registro = { token: string; membro_id: string; casa_id: string; lista_id: string | null };
export type Eu = {
  membro: { id: string; apelido: string; papel: "dono" | "membro" };
  casa: { id: string; bairro_id: string | null; membros: { id: string; apelido: string; papel: string }[] };
  listas: { id: string; nome: string }[];
};
export type TipoOperacao = "criar" | "somar" | "tirar" | "marcar" | "desmarcar" | "remover";
export type Operacao = {
  id: string;
  item_id: string;
  tipo: TipoOperacao;
  feita_em: string; // ISO 8601 com fuso
  valor?: number;
  produto_id?: string;
  categoria_id?: string;
};
export type ItemDaLista = {
  id: string;
  quantidade: number;
  comprado: boolean;
  aviso: string | null;
  adicionado_por: string | null;
  produto_id: string | null;
  nome: string | null;
  marca: string | null;
  categoria: string | null;
};
export type LojaComparada = {
  loja_id: string;
  rede: string;
  nome: string;
  distancia_km: number;
  total_centavos: number;
  fora_da_soma: string[];
  comparacao_parcial: boolean;
  preco_mais_antigo_em: string | null;
  algum_preco_pode_ter_mudado: boolean;
};
export type Comparacao = {
  comuns: number;
  lojas: LojaComparada[];
  divisao: null | {
    lojas: [string, string];
    total_centavos: number;
    economia_centavos: number;
    custo_deslocamento_centavos: number;
    compensa: boolean;
  };
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

  convidar: () => pedir<{ codigo: string; expira_em: string; usos_restantes: number }>("POST", "/v1/casa/convites"),
  eu: () => pedir<Eu>("GET", "/v1/eu"),

  async excluirConta(): Promise<void> {
    await pedir<void>("DELETE", "/v1/eu");
    await esquecerToken();
  },

  enviarOperacoes: (listaId: string, operacoes: Operacao[]) =>
    pedir<{ recebidas: number; novas: number; cursor: number }>("POST", `/v1/listas/${listaId}/operacoes`, { operacoes }),
  operacoesDesde: (listaId: string, cursor: number) =>
    pedir<{ operacoes: (Operacao & { seq: number })[]; cursor: number }>("GET", `/v1/listas/${listaId}/operacoes?desde=${cursor}`),
  lista: (listaId: string) => pedir<{ itens: ItemDaLista[]; cursor: number }>("GET", `/v1/listas/${listaId}`),
  comparar: (bairroId: string, listaId: string) =>
    pedir<Comparacao>("POST", "/v1/comparar", { bairro_id: bairroId, lista_id: listaId }),
};
