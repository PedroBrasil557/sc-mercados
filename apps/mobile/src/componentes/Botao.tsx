import { ActivityIndicator, Pressable, StyleSheet, Text } from "react-native";

import { fonte, useTema } from "@/tema";

type Props = {
  rotulo: string;
  aoTocar: () => void;
  tipo?: "principal" | "secundario";
  ocupado?: boolean;
  desativado?: boolean;
};

/** Botão de 48 dp de altura (alvo de toque mínimo do Android). */
export function Botao({ rotulo, aoTocar, tipo = "principal", ocupado = false, desativado = false }: Props) {
  const { cor } = useTema();
  const principal = tipo === "principal";
  const inativo = desativado || ocupado;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      accessibilityState={{ disabled: inativo, busy: ocupado }}
      disabled={inativo}
      onPress={aoTocar}
      style={({ pressed }) => [
        estilos.botao,
        principal ? { backgroundColor: cor.marcaEtiqueta } : { borderWidth: 1, borderColor: cor.bordaForte },
        (pressed || inativo) && { opacity: 0.6 },
      ]}
    >
      {ocupado ? (
        <ActivityIndicator color={principal ? cor.marcaSobreEtiqueta : cor.textoPrincipal} />
      ) : (
        <Text style={[fonte("botao"), { color: principal ? cor.marcaSobreEtiqueta : cor.textoPrincipal }]}>{rotulo}</Text>
      )}
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  botao: { minHeight: 48, borderRadius: 24, paddingHorizontal: 20, alignItems: "center", justifyContent: "center" },
});
