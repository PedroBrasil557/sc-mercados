/**
 * Tema do app: cores do modo claro/escuro do aparelho e estilos de texto prontos para o React Native.
 * Os valores vêm de @quantofica/tema, gerado a partir das variáveis do Figma.
 */
import { tema, tipografia, type ModoTema } from "@quantofica/tema";
import type { TextStyle } from "react-native";
import { useColorScheme } from "react-native";

export type EstiloTexto = keyof typeof tipografia;
export type Tema = ReturnType<typeof tema>;

// Nome de cada peso carregado por useFonts no _layout raiz.
const FAMILIAS: Record<string, Record<number, string>> = {
  "Bricolage Grotesque": { 600: "BricolageGrotesque_600SemiBold", 700: "BricolageGrotesque_700Bold", 800: "BricolageGrotesque_800ExtraBold" },
  Figtree: { 400: "Figtree_400Regular", 500: "Figtree_500Medium", 600: "Figtree_600SemiBold", 700: "Figtree_700Bold" },
  "IBM Plex Mono": { 500: "IBMPlexMono_500Medium" },
};

export function fonte(estilo: EstiloTexto): TextStyle {
  const t = tipografia[estilo];
  const familia = FAMILIAS[t.familia]?.[t.peso];
  if (!familia) throw new Error(`Fonte não carregada: ${t.familia} ${t.peso}`);
  return {
    fontFamily: familia,
    fontSize: t.tamanho,
    lineHeight: t.altura,
    letterSpacing: t.espacamento,
    ...("caixa" in t && t.caixa === "alta" ? { textTransform: "uppercase" as const } : {}),
  };
}

export function useTema(): Tema & { modo: ModoTema } {
  const modo: ModoTema = useColorScheme() === "dark" ? "escuro" : "claro";
  return { ...tema(modo), modo };
}
