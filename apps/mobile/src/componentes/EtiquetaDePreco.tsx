import { StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

/** Elemento-assinatura (Figma "Etiqueta de preço"): amarela, 24 dp, furo de 6 dp. Uma por tela, só no destaque. */
export function EtiquetaDePreco({ texto = "Mais barato" }: { texto?: string }) {
  const { cor } = useTema();
  return (
    <View style={[estilos.etiqueta, { backgroundColor: cor.marcaEtiqueta }]}>
      <View style={[estilos.furo, { backgroundColor: cor.fundoSuperficie }]} />
      <Text numberOfLines={1} style={[fonte("rotulo"), { color: cor.marcaSobreEtiqueta }]}>
        {texto}
      </Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  etiqueta: { height: 24, borderRadius: 6, paddingLeft: 20, paddingRight: 12, flexDirection: "row", alignItems: "center" },
  furo: { position: "absolute", left: 8, top: 9, width: 6, height: 6, borderRadius: 3 },
});
