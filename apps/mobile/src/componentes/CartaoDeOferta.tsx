import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Oferta } from "@/api/cliente";
import { reais, tamanho } from "@/formatar";
import { fonte, useTema } from "@/tema";

import { Miniatura } from "./Miniatura";

/** Figma "Cartão de oferta" (R9): miniatura M, selo amarelo com o desconto, preço atual e o anterior riscado. */
export function CartaoDeOferta({ oferta, aoTocar }: { oferta: Oferta; aoTocar: () => void }) {
  const { cor } = useTema();
  const p = oferta.produto;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${p.nome}, menos ${oferta.desconto_pct}%, ${reais(oferta.preco_centavos)} no ${oferta.rede} ${oferta.bairro ?? ""}`}
      onPress={aoTocar}
      style={({ pressed }) => [estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }, pressed && { opacity: 0.9 }]}
    >
      <Miniatura porte="M" categoria={p.categoria} marca={p.marca} tamanho={tamanho(p.tamanho, p.unidade)} nome={p.nome} />
      <View style={[estilos.desconto, { backgroundColor: cor.marcaEtiqueta }]}>
        <Text style={[fonte("rotulo"), { color: cor.marcaSobreEtiqueta }]}>−{oferta.desconto_pct}%</Text>
      </View>
      <View style={estilos.corpo}>
        <Text numberOfLines={2} style={[fonte("corpoMenor"), { color: cor.textoPrincipal }]}>
          {p.nome}
        </Text>
        <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.textoSuave }]}>
          {oferta.rede} · {oferta.bairro ?? oferta.nome}
        </Text>
        <View style={estilos.preco}>
          <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal }]}>{reais(oferta.preco_centavos)}</Text>
          <Text style={[fonte("legenda"), { color: cor.textoSuave, textDecorationLine: "line-through" }]}>
            {reais(oferta.referencia_centavos)}
          </Text>
        </View>
      </View>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  cartao: { flex: 1, minHeight: 240, borderRadius: 18, borderWidth: 1, overflow: "hidden" },
  desconto: { position: "absolute", left: 9, top: 9, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  corpo: { paddingTop: 12, paddingBottom: 16, paddingHorizontal: 12, gap: 4 },
  preco: { flexDirection: "row", alignItems: "baseline", gap: 8, flexWrap: "wrap" },
});
