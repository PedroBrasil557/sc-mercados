import { Pressable, StyleSheet, Text } from "react-native";

import { fonte, useTema } from "@/tema";

/** Figma "Chip": 36 dp (toque de 48), padding 16. Ativo: fundo profundo. Inativo: superfície com borda. */
export function Chip({ texto, ativo = false, aoTocar }: { texto: string; ativo?: boolean; aoTocar: () => void }) {
  const { cor } = useTema();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={texto}
      hitSlop={6}
      onPress={aoTocar}
      style={({ pressed }) => [
        estilos.chip,
        ativo ? { backgroundColor: cor.fundoProfundo } : { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderWidth: 1 },
        pressed && { opacity: 0.8 },
      ]}
    >
      <Text style={[fonte("corpoMenor"), { color: ativo ? cor.textoInverso : cor.textoPrincipal }]}>{texto}</Text>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  chip: { height: 36, borderRadius: 18, paddingHorizontal: 16, justifyContent: "center" },
});
