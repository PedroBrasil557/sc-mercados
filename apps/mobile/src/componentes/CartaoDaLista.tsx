import { Pressable, StyleSheet, Text, View } from "react-native";

import type { Comparacao } from "@/api/cliente";
import { diferenca, reais, seloDeFonte } from "@/formatar";
import { fonte, useTema } from "@/tema";

import { EtiquetaDePreco } from "./EtiquetaDePreco";
import { Icone } from "./Icone";

/** Figma "Cartão da lista" (Início): total no mercado mais barato e quanto a mais custa nos outros. */
export function CartaoDaLista({ rotulo, comparacao, aoComparar }: { rotulo: string; comparacao: Comparacao; aoComparar: () => void }) {
  const { cor } = useTema();
  const [primeira, ...outras] = comparacao.lojas;
  if (!primeira) return null;
  const selo = primeira.preco_mais_antigo_em ? `${seloDeFonte("site", primeira.preco_mais_antigo_em)} · SEM TAXA` : "SEM TAXA";
  return (
    <View style={[estilos.cartao, { backgroundColor: cor.fundoProfundo }]}>
      <Text style={[fonte("rotulo"), { color: cor.textoInverso }]}>{rotulo}</Text>
      <Text style={[fonte("precoGrande"), { color: cor.textoInverso }]}>{reais(primeira.total_centavos)}</Text>
      <View style={estilos.onde}>
        <Text numberOfLines={1} style={[fonte("corpoForte"), { color: cor.textoInverso, flexShrink: 1 }]}>
          no {primeira.nome}
        </Text>
        {outras.length ? <EtiquetaDePreco /> : null}
      </View>
      {outras.length ? <View style={[estilos.divisoria, { backgroundColor: cor.sobreposicaoDivisor }]} /> : null}
      {outras.slice(0, 3).map((l) => (
        <View key={l.loja_id} style={estilos.outra}>
          <Text numberOfLines={1} style={[fonte("corpoMenor"), { color: cor.textoInverso, flexShrink: 1 }]}>
            {l.nome}
          </Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoInverso }]}>{diferenca(l.total_centavos - primeira.total_centavos)}</Text>
        </View>
      ))}
      <View style={estilos.rodape}>
        <Text style={[fonte("seloDeFonte"), { color: cor.textoInverso, flexShrink: 1 }]}>{selo}</Text>
        <Pressable accessibilityRole="link" accessibilityLabel="Ver a comparação completa" hitSlop={10} onPress={aoComparar} style={estilos.comparar}>
          <Text style={[fonte("corpoForte"), { color: cor.marcaEtiqueta }]}>Comparar</Text>
          <Icone nome="seta-direita" cor={cor.marcaEtiqueta} tamanho={20} />
        </Pressable>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  cartao: { borderRadius: 24, paddingTop: 20, paddingBottom: 16, paddingHorizontal: 20, gap: 8 },
  onde: { flexDirection: "row", alignItems: "center", gap: 12 },
  divisoria: { height: 1 },
  outra: { flexDirection: "row", justifyContent: "space-between", gap: 12 },
  rodape: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingTop: 8, gap: 12 },
  comparar: { flexDirection: "row", alignItems: "center", gap: 2, minHeight: 44 },
});
