import type { ReactNode } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fonte, useTema } from "@/tema";

type Props = { visivel: boolean; titulo: string; aoFechar: () => void; children: ReactNode; rodape?: ReactNode };

/** Painel de baixo do Figma (telas 17, 18, 19, 22): véu, alça, título, conteúdo rolável e ação no pé. */
export function PainelInferior({ visivel, titulo, aoFechar, children, rodape }: Props) {
  const { cor, medida } = useTema();
  const margem = useSafeAreaInsets();
  return (
    <Modal visible={visivel} transparent animationType="slide" onRequestClose={aoFechar} statusBarTranslucent navigationBarTranslucent>
      <Pressable accessibilityLabel="Fechar" style={[StyleSheet.absoluteFill, { backgroundColor: cor.sobreposicaoVeu }]} onPress={aoFechar} />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={estilos.base} pointerEvents="box-none">
        <View
          style={[
            estilos.painel,
            { backgroundColor: cor.fundoSuperficie, borderTopLeftRadius: medida.raioTela, borderTopRightRadius: medida.raioTela, paddingBottom: margem.bottom + 20 },
          ]}
        >
          <View style={[estilos.alca, { backgroundColor: cor.bordaPadrao }]} />
          <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
            {titulo}
          </Text>
          <ScrollView style={{ flexGrow: 0 }} contentContainerStyle={{ gap: 12 }} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
          {rodape}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  base: { flex: 1, justifyContent: "flex-end" },
  painel: { maxHeight: "88%", paddingTop: 12, paddingHorizontal: 24, gap: 16 },
  alca: { alignSelf: "center", width: 40, height: 5, borderRadius: 3 },
});
