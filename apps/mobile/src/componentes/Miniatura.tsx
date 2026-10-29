import { categorias, type Categoria } from "@quantofica/tema";
import { StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

import { IconeDeCategoria } from "./Icone";

const ehCategoria = (c: string | null): c is Categoria => !!c && (categorias as readonly string[]).includes(c);

const capitalizar = (c: Categoria) => (c.charAt(0).toUpperCase() + c.slice(1)) as Capitalize<Categoria>;

/**
 * Miniatura do produto sem foto (Figma "Miniatura do produto", tamanho P, 52 dp): ícone e cores da
 * categoria e o tamanho. O nome do produto fica fora, onde a tela já o mostra.
 */
export function Miniatura({ categoria, tamanho, nome }: { categoria: string | null; tamanho: string | null; nome: string }) {
  const { cor } = useTema();
  const cat: Categoria = ehCategoria(categoria) ? categoria : "mercearia";
  const fundo = cor[`categoria${capitalizar(cat)}Fundo`];
  const tinta = cor[`categoria${capitalizar(cat)}Tinta`];
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

const estilos = StyleSheet.create({
  p: { width: 52, height: 52, borderRadius: 12, alignItems: "center", justifyContent: "center", gap: 2 },
});
