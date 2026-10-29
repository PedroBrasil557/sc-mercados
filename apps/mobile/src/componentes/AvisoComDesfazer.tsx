import { useEffect } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

/** 25 Aviso com desfazer: barra escura no pé da tela por 5 s. */
export function AvisoComDesfazer({ texto, aoDesfazer, aoSumir }: { texto: string; aoDesfazer: () => void; aoSumir: () => void }) {
  const { cor } = useTema();
  useEffect(() => {
    const relogio = setTimeout(aoSumir, 5000);
    return () => clearTimeout(relogio);
  }, [texto, aoSumir]);
  return (
    <View accessibilityLiveRegion="polite" style={[estilos.aviso, { backgroundColor: cor.fundoProfundo }]}>
      <Text numberOfLines={2} style={[fonte("corpoMenor"), { color: cor.textoInverso, flex: 1 }]}>
        {texto}
      </Text>
      <Pressable accessibilityRole="button" onPress={aoDesfazer} hitSlop={8} style={estilos.botao}>
        <Text style={[fonte("botao"), { color: cor.marcaEtiqueta }]}>Desfazer</Text>
      </Pressable>
    </View>
  );
}

const estilos = StyleSheet.create({
  aviso: { flexDirection: "row", alignItems: "center", gap: 12, paddingLeft: 20, paddingRight: 8, minHeight: 56, borderRadius: 16 },
  botao: { minHeight: 44, paddingHorizontal: 12, justifyContent: "center" },
});
