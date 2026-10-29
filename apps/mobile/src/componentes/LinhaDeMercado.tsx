import { Pressable, StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

import { EtiquetaDePreco } from "./EtiquetaDePreco";

type Props = {
  rede: string;
  detalhe: string; // "Victor Konder · 0,8 km"
  total: string;
  diferenca?: string; // destaque: "R$ 30,74 a menos"; demais: "+R$ 0,06"
  destaque?: boolean;
  etiqueta?: string; // "Mais barato" ou "Melhor para você"
  nota?: string | null; // por que uma loja mais barata não foi a escolhida
  aoTocar?: () => void;
};

/** Total da lista numa loja (R7, R13). Destaque só na mais barata, com a etiqueta MAIS BARATO. */
export function LinhaDeMercado({ rede, detalhe, total, diferenca, destaque = false, etiqueta = "Mais barato", nota, aoTocar }: Props) {
  const { cor, medida } = useTema();
  return (
    <Pressable
      disabled={!aoTocar}
      onPress={aoTocar}
      accessibilityRole={aoTocar ? "button" : "text"}
      accessibilityHint={aoTocar ? "Toque para ver as outras lojas da rede" : undefined}
      accessibilityLabel={`${rede}${destaque ? `, ${etiqueta.toLowerCase()}` : ""}, ${total}. ${detalhe}${diferenca ? `. ${diferenca}` : ""}${nota ? `. ${nota}` : ""}`}
      style={({ pressed }) => [
        estilos.linha,
        { borderRadius: medida.raioMedio + 2 },
        destaque
          ? { backgroundColor: cor.estadoEconomiaSuave, borderColor: cor.estadoEconomia, borderWidth: 1.5 }
          : { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderWidth: 1 },
        pressed && { opacity: 0.85 },
      ]}
    >
      <View style={[estilos.monograma, { backgroundColor: destaque ? cor.fundoSuperficie : cor.fundoAfundado }]}>
        <Text style={[fonte("numeroMonograma"), { color: cor.textoPrincipal }]}>{rede.charAt(0)}</Text>
      </View>
      <View style={estilos.mercado}>
        <View style={estilos.nome}>
          <Text numberOfLines={1} style={[fonte("corpoForte"), { color: cor.textoPrincipal, flexShrink: 1 }]}>
            {rede}
          </Text>
          {destaque ? <EtiquetaDePreco texto={etiqueta} /> : null}
        </View>
        <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.textoSuave }]}>
          {detalhe}
        </Text>
        {nota ? <Text style={[fonte("legenda"), { color: cor.textoSuave, fontStyle: "italic" }]}>{nota}</Text> : null}
      </View>
      <View style={estilos.total}>
        <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal, fontVariant: ["tabular-nums"] }]}>{total}</Text>
        {diferenca ? <Text style={[fonte("legenda"), { color: destaque ? cor.estadoEconomia : cor.textoSuave }]}>{diferenca}</Text> : null}
      </View>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  linha: { minHeight: 72, padding: 16, flexDirection: "row", alignItems: "center", gap: 12 },
  monograma: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  mercado: { flex: 1, gap: 2 },
  nome: { flexDirection: "row", alignItems: "center", gap: 8 },
  total: { alignItems: "flex-end", gap: 2 },
});
