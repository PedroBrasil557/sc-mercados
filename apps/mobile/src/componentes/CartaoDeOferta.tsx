import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Oferta } from "@/api/cliente";
import { reais, tamanho } from "@/formatar";
import { fonte, useTema } from "@/tema";

import { Icone } from "./Icone";
import { Miniatura } from "./Miniatura";

/** Figma "Cartão de oferta" (R9): miniatura M, selo amarelo com o desconto, preço atual e o anterior riscado,
 * preço por kg/l embaixo e "+" no canto para pôr na lista sem abrir o produto. */
export function CartaoDeOferta({ oferta, aoTocar, aoPor }: { oferta: Oferta; aoTocar: () => void; aoPor?: () => void }) {
  const { cor } = useTema();
  const p = oferta.produto;
  const nome = p.nome_curto ? `${p.nome_curto}${p.marca ? ` ${p.marca}` : ""} ${tamanho(p.tamanho, p.unidade) ?? ""}`.trim() : p.nome;
  const encarte = oferta.fonte === "encarte";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${nome}, ${encarte ? "no encarte" : `menos ${oferta.desconto_pct}%`}, ${reais(oferta.preco_centavos)} no ${oferta.rede} ${oferta.bairro ?? ""}`}
      onPress={aoTocar}
      style={({ pressed }) => [estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }, pressed && { opacity: 0.9 }]}
    >
      <Miniatura porte="M" categoria={p.categoria} marca={p.marca} tamanho={tamanho(p.tamanho, p.unidade)} nome={p.nome} />
      <View style={[estilos.desconto, { backgroundColor: cor.marcaEtiqueta }]}>
        <Text style={[fonte("rotulo"), { color: cor.marcaSobreEtiqueta }]}>{encarte ? "ENCARTE" : `−${oferta.desconto_pct}%`}</Text>
      </View>
      {aoPor ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Pôr ${nome} na lista`}
          hitSlop={6}
          onPress={aoPor}
          style={({ pressed }) => [estilos.mais, { backgroundColor: cor.fundoProfundo }, pressed && { opacity: 0.85 }]}
        >
          <Icone nome="mais" cor={cor.textoInverso} tamanho={20} />
        </Pressable>
      ) : null}
      <View style={estilos.corpo}>
        <Text numberOfLines={2} style={[fonte("corpoMenor"), { color: cor.textoPrincipal }]}>
          {nome}
        </Text>
        <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.textoSuave }]}>
          {oferta.rede} · {oferta.bairro ?? oferta.nome}
        </Text>
        <View style={estilos.preco}>
          <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal }]}>{reais(oferta.preco_centavos)}</Text>
          <Text style={[fonte("legenda"), { color: cor.textoSuave, textDecorationLine: "line-through" }]}>{reais(oferta.referencia_centavos)}</Text>
        </View>
        {oferta.preco_por_unidade ? <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{oferta.preco_por_unidade}</Text> : null}
      </View>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  cartao: { flex: 1, minHeight: 240, borderRadius: 18, borderWidth: 1, overflow: "hidden" },
  desconto: { position: "absolute", left: 9, top: 9, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  mais: { position: "absolute", right: 9, top: 9, width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  corpo: { paddingTop: 12, paddingBottom: 16, paddingHorizontal: 12, gap: 4 },
  preco: { flexDirection: "row", alignItems: "baseline", gap: 8, flexWrap: "wrap" },
});
