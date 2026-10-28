import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fonte, useTema } from "@/tema";

/**
 * Esqueleto de tela. As telas completas entram depois do teste com as famílias;
 * até lá cada aba mostra o título e o que ela vai fazer.
 */
export function TelaProvisoria({ titulo, descricao }: { titulo: string; descricao: string }) {
  const { cor, medida } = useTema();
  const margem = useSafeAreaInsets();
  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + medida.espaco6, paddingHorizontal: medida.espaco5 }]}>
      <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
        {titulo}
      </Text>
      <View
        style={[
          estilos.cartao,
          { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderRadius: medida.raioMedio, padding: medida.espaco4 },
        ]}
      >
        <Text style={[fonte("rotulo"), { color: cor.textoSuave }]}>Em construção</Text>
        <Text style={[fonte("corpoPadrao"), { color: cor.textoPrincipal }]}>{descricao}</Text>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1, gap: 16 },
  cartao: { borderWidth: StyleSheet.hairlineWidth, gap: 6 },
});
