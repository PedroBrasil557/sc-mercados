import { categorias, type Categoria } from "@quantofica/tema";
import { StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

import { IconeDeCategoria } from "./Icone";

const ehCategoria = (c: string | null): c is Categoria => !!c && (categorias as readonly string[]).includes(c);
const capitalizar = (c: Categoria) => (c.charAt(0).toUpperCase() + c.slice(1)) as Capitalize<Categoria>;

type Props = {
  categoria: string | null;
  tamanho: string | null;
  nome: string;
  marca?: string | null;
  /** P (52 dp) na lista; M (cartão de oferta); G (topo do detalhe). */
  porte?: "P" | "M" | "G";
};

/**
 * Figma "Miniatura do produto" sem foto: cores e ícone da categoria, marca escrita (nunca logotipo) e tamanho.
 * O nome do produto fica fora, onde a tela já o mostra; aqui ele é só o texto lido pelo leitor de tela.
 */
export function Miniatura({ categoria, tamanho, nome, marca, porte = "P" }: Props) {
  const { cor } = useTema();
  const cat: Categoria = ehCategoria(categoria) ? categoria : "mercearia";
  const fundo = cor[`categoria${capitalizar(cat)}Fundo`];
  const tinta = cor[`categoria${capitalizar(cat)}Tinta`];

  if (porte === "P") {
    return (
      <View accessible accessibilityRole="image" accessibilityLabel={nome} style={[estilos.p, { backgroundColor: fundo }]}>
        <IconeDeCategoria categoria={cat} cor={tinta} tamanho={20} />
        {tamanho ? (
          <Text numberOfLines={1} style={[fonte("numeroTamanho"), { color: tinta }]}>
            {tamanho}
          </Text>
        ) : null}
      </View>
    );
  }

  const grande = porte === "G";
  return (
    <View accessible accessibilityRole="image" accessibilityLabel={nome} style={[grande ? estilos.g : estilos.m, { backgroundColor: fundo }]}>
      <View style={[grande ? estilos.emblemaG : estilos.emblemaM, { backgroundColor: cor.sobreposicaoVidro }]}>
        <IconeDeCategoria categoria={cat} cor={tinta} tamanho={grande ? 40 : 32} />
      </View>
      <View style={estilos.marca}>
        {marca ? <Text style={[fonte(grande ? "corpoForte" : "rotulo"), { color: tinta, textTransform: "uppercase", letterSpacing: 0.8 }]}>{marca}</Text> : null}
        {tamanho ? (
          <View style={[estilos.selo, { backgroundColor: cor.fundoSuperficie }]}>
            <Text style={[fonte("numeroTamanho"), { color: cor.textoPrincipal }]}>{tamanho}</Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  p: { width: 52, height: 52, borderRadius: 12, alignItems: "center", justifyContent: "center", gap: 2 },
  m: { height: 116, alignItems: "center", justifyContent: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 10 },
  g: { height: 300, alignItems: "center", justifyContent: "center", gap: 12 },
  emblemaM: { width: 60, height: 60, borderRadius: 30, alignItems: "center", justifyContent: "center" },
  emblemaG: { width: 140, height: 140, borderRadius: 70, alignItems: "center", justifyContent: "center" },
  marca: { flexDirection: "row", alignItems: "center", gap: 8 },
  selo: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
});
