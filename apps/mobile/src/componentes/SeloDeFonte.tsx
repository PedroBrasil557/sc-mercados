import { StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

/** De onde veio o preço e quando foi conferido (R6). Sempre ao lado de um total ou preço, nunca sozinho. */
export function SeloDeFonte({ texto }: { texto: string }) {
  const { cor } = useTema();
  return (
    <View style={[estilos.selo, { backgroundColor: cor.fundoAfundado }]}>
      <Text style={[fonte("seloDeFonte"), { color: cor.textoSuave }]}>{texto}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  selo: { alignSelf: "flex-start", borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
});
