/**
 * Tokens do Quanto Fica, exportados do Figma (variáveis).
 * Fonte da verdade: arquivo "Quanto Fica — App MVP", página "Fundamentos e componentes".
 * Não edite à mão: mude no Figma, atualize tokens.json e rode `python gerar_tema.py`.
 *
 * Nome no Figma → nome no código:
 *   fundoTela = fundo/tela
 *   fundoSuperficie = fundo/superficie
 *   fundoAfundado = fundo/afundado
 *   fundoProfundo = fundo/profundo
 *   textoPrincipal = texto/principal
 *   textoSuave = texto/suave
 *   textoInverso = texto/inverso
 *   bordaPadrao = borda/padrao
 *   bordaForte = borda/forte
 *   marcaEtiqueta = marca/etiqueta
 *   marcaSobreEtiqueta = marca/sobre-etiqueta
 *   estadoEconomia = estado/economia
 *   estadoEconomiaSuave = estado/economia-suave
 *   estadoSobreEconomia = estado/sobre-economia
 *   estadoAlerta = estado/alerta
 *   estadoAlertaSuave = estado/alerta-suave
 *   avisoAcao = aviso/acao
 *   sobreposicaoVidro = sobreposicao/vidro
 *   sobreposicaoDivisor = sobreposicao/divisor
 *   sobreposicaoVeu = sobreposicao/veu
 *   categoriaLaticiniosFundo = categoria/laticinios/fundo
 *   categoriaLaticiniosTinta = categoria/laticinios/tinta
 *   categoriaCafeFundo = categoria/cafe/fundo
 *   categoriaCafeTinta = categoria/cafe/tinta
 *   categoriaGraosFundo = categoria/graos/fundo
 *   categoriaGraosTinta = categoria/graos/tinta
 *   categoriaBebidasFundo = categoria/bebidas/fundo
 *   categoriaBebidasTinta = categoria/bebidas/tinta
 *   categoriaDocesFundo = categoria/doces/fundo
 *   categoriaDocesTinta = categoria/doces/tinta
 *   categoriaMerceariaFundo = categoria/mercearia/fundo
 *   categoriaMerceariaTinta = categoria/mercearia/tinta
 *   categoriaHigieneFundo = categoria/higiene/fundo
 *   categoriaHigieneTinta = categoria/higiene/tinta
 *   categoriaLimpezaFundo = categoria/limpeza/fundo
 *   categoriaLimpezaTinta = categoria/limpeza/tinta
 *   categoriaPadariaFundo = categoria/padaria/fundo
 *   categoriaPadariaTinta = categoria/padaria/tinta
 *   categoriaHortifrutiFundo = categoria/hortifruti/fundo
 *   categoriaHortifrutiTinta = categoria/hortifruti/tinta
 */

export const corClaro = {
  fundoTela: "#F2F4EF",
  fundoSuperficie: "#FFFFFF",
  fundoAfundado: "#E8ECE5",
  fundoProfundo: "#0F3B2E",
  textoPrincipal: "#14231D",
  textoSuave: "#5B6A62",
  textoInverso: "#FFFFFF",
  bordaPadrao: "#D7DDD4",
  bordaForte: "#77857D",
  marcaEtiqueta: "#FFD43B",
  marcaSobreEtiqueta: "#14231D",
  estadoEconomia: "#0E7553",
  estadoEconomiaSuave: "#DDF2E8",
  estadoSobreEconomia: "#FFFFFF",
  estadoAlerta: "#C2412D",
  estadoAlertaSuave: "#FBE6E1",
  avisoAcao: "#FFD43B",
  sobreposicaoVidro: "rgba(255,255,255,0.14)",
  sobreposicaoDivisor: "rgba(255,255,255,0.18)",
  sobreposicaoVeu: "rgba(13,26,20,0.5)",
  categoriaLaticiniosFundo: "#E6EEF7",
  categoriaLaticiniosTinta: "#2F5A86",
  categoriaCafeFundo: "#F1E7DE",
  categoriaCafeTinta: "#6B4426",
  categoriaGraosFundo: "#EEF0DA",
  categoriaGraosTinta: "#5A5E14",
  categoriaBebidasFundo: "#F8E3E0",
  categoriaBebidasTinta: "#9A2F25",
  categoriaDocesFundo: "#F6E6EF",
  categoriaDocesTinta: "#8A2F5E",
  categoriaMerceariaFundo: "#FBE7D6",
  categoriaMerceariaTinta: "#8F4A12",
  categoriaHigieneFundo: "#ECE8F6",
  categoriaHigieneTinta: "#4F3E8C",
  categoriaLimpezaFundo: "#E1F2F1",
  categoriaLimpezaTinta: "#1F6B66",
  categoriaPadariaFundo: "#F6EBD9",
  categoriaPadariaTinta: "#7A5216",
  categoriaHortifrutiFundo: "#E5F2E1",
  categoriaHortifrutiTinta: "#2F6B2A",
} as const;

export const corEscuro: Record<keyof typeof corClaro, string> = {
  fundoTela: "#0E1512",
  fundoSuperficie: "#17201B",
  fundoAfundado: "#121915",
  fundoProfundo: "#14412F",
  textoPrincipal: "#EAF0EA",
  textoSuave: "#9DAAA2",
  textoInverso: "#F2F4EF",
  bordaPadrao: "#2A352F",
  bordaForte: "#6B7972",
  marcaEtiqueta: "#F5C928",
  marcaSobreEtiqueta: "#0E1512",
  estadoEconomia: "#4CC79A",
  estadoEconomiaSuave: "#163A2C",
  estadoSobreEconomia: "#0E1512",
  estadoAlerta: "#F07B6A",
  estadoAlertaSuave: "#3A1F1A",
  avisoAcao: "#0E7553",
  sobreposicaoVidro: "rgba(255,255,255,0.12)",
  sobreposicaoDivisor: "rgba(255,255,255,0.16)",
  sobreposicaoVeu: "rgba(0,0,0,0.6)",
  categoriaLaticiniosFundo: "#2D3A3C",
  categoriaLaticiniosTinta: "#9EC1E8",
  categoriaCafeFundo: "#36372D",
  categoriaCafeTinta: "#D9B08C",
  categoriaGraosFundo: "#333C2A",
  categoriaGraosTinta: "#C9CD7A",
  categoriaBebidasFundo: "#3A342F",
  categoriaBebidasTinta: "#F0A096",
  categoriaDocesFundo: "#383536",
  categoriaDocesTinta: "#E7A3C6",
  categoriaMerceariaFundo: "#3A382A",
  categoriaMerceariaTinta: "#F2B37A",
  categoriaHigieneFundo: "#31363C",
  categoriaHigieneTinta: "#B9ACEB",
  categoriaLimpezaFundo: "#293D37",
  categoriaLimpezaTinta: "#86D3CC",
  categoriaPadariaFundo: "#383A2B",
  categoriaPadariaTinta: "#E5C07D",
  categoriaHortifrutiFundo: "#2C3D2E",
  categoriaHortifrutiTinta: "#9CD38F",
};

/** Categorias da miniatura do produto (fundo + tinta de cada uma). */
export const categorias = ["bebidas", "cafe", "doces", "graos", "higiene", "hortifruti", "laticinios", "limpeza", "mercearia", "padaria"] as const;
export type Categoria = (typeof categorias)[number];

/** Escala de 4 dp: espaco1 = 4, espaco2 = 8 ... espaco8 = 32. */
export const medida = {
  espaco1: 4,
  espaco2: 8,
  espaco3: 12,
  espaco4: 16,
  espaco5: 20,
  espaco6: 24,
  espaco8: 32,
  raioPequeno: 8,
  raioMedio: 14,
  raioGrande: 20,
  raioTela: 28,
  raioPilula: 999,
} as const;

/** Durações em ms; curvas como cubic-bezier (x1, y1, x2, y2). */
export const movimento = {
  duracaoCurta: 120,
  duracaoPadrao: 240,
  duracaoLonga: 320,
  duracaoBrilho: 1200,
  curvaPadrao: [0.2, 0, 0, 1] as const,
  curvaEntrada: [0.05, 0.7, 0.1, 1] as const,
  curvaSaida: [0.3, 0, 0.8, 0.15] as const,
};

export const tipografia = {
  displayGrande: {
    familia: "Bricolage Grotesque",
    peso: 800,
    tamanho: 34,
    altura: 38,
    espacamento: -1.5,
  },
  displayMedio: {
    familia: "Bricolage Grotesque",
    peso: 700,
    tamanho: 26,
    altura: 30,
    espacamento: -1,
  },
  tituloTela: {
    familia: "Bricolage Grotesque",
    peso: 700,
    tamanho: 22,
    altura: 28,
    espacamento: -0.5,
  },
  tituloSecao: {
    familia: "Bricolage Grotesque",
    peso: 600,
    tamanho: 18,
    altura: 24,
    espacamento: -0.3,
  },
  precoGrande: {
    familia: "Bricolage Grotesque",
    peso: 800,
    tamanho: 30,
    altura: 34,
    espacamento: -1,
  },
  precoMedio: {
    familia: "Bricolage Grotesque",
    peso: 700,
    tamanho: 18,
    altura: 22,
    espacamento: -0.3,
  },
  corpoForte: {
    familia: "Figtree",
    peso: 600,
    tamanho: 16,
    altura: 22,
    espacamento: 0,
  },
  corpoPadrao: {
    familia: "Figtree",
    peso: 400,
    tamanho: 16,
    altura: 22,
    espacamento: 0,
  },
  corpoMenor: {
    familia: "Figtree",
    peso: 500,
    tamanho: 14,
    altura: 20,
    espacamento: 0,
  },
  legenda: {
    familia: "Figtree",
    peso: 500,
    tamanho: 12,
    altura: 16,
    espacamento: 0,
  },
  rotulo: {
    familia: "Figtree",
    peso: 700,
    tamanho: 11,
    altura: 14,
    espacamento: 0.8,
    caixa: "alta",
  },
  botao: {
    familia: "Figtree",
    peso: 700,
    tamanho: 16,
    altura: 20,
    espacamento: 0,
  },
  seloDeFonte: {
    familia: "IBM Plex Mono",
    peso: 500,
    tamanho: 11,
    altura: 14,
    espacamento: 0.2,
  },
  navegacaoRotulo: {
    familia: "Figtree",
    peso: 500,
    tamanho: 12,
    altura: 16,
    espacamento: 0,
  },
  navegacaoAtivo: {
    familia: "Figtree",
    peso: 700,
    tamanho: 12,
    altura: 16,
    espacamento: 0,
  },
  numeroQuantidade: {
    familia: "Bricolage Grotesque",
    peso: 700,
    tamanho: 16,
    altura: 20,
    espacamento: 0,
  },
  cupomLinha: {
    familia: "IBM Plex Mono",
    peso: 500,
    tamanho: 12,
    altura: 16,
    espacamento: 0,
  },
  numeroTamanho: {
    familia: "Figtree",
    peso: 700,
    tamanho: 12,
    altura: 16,
    espacamento: 0,
  },
} as const;

export type ModoTema = "claro" | "escuro";
export type Cor = keyof typeof corClaro;

export function tema(modo: ModoTema) {
  return { cor: modo === "escuro" ? corEscuro : corClaro, medida, movimento, tipografia };
}
