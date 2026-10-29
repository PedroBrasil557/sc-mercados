import { ActivityIndicator, Pressable, StyleSheet, Text } from "react-native";

import { fonte, useTema } from "@/tema";

type Props = {
  rotulo: string;
  aoTocar: () => void;
  /** Figma "Botão": primário (ação principal, uma por tela), etiqueta (economia/mercado), contorno (secundária). */
  tipo?: "primario" | "etiqueta" | "contorno";
  ocupado?: boolean;
  desativado?: boolean;
  largo?: boolean;
};

/** Botão em pílula: 52 dp, padding 24, texto Botão. Pressionado escurece; desativado fica a 40%. */
export function Botao({ rotulo, aoTocar, tipo = "primario", ocupado = false, desativado = false, largo = false }: Props) {
  const { cor } = useTema();
  const fundo = tipo === "primario" ? cor.fundoProfundo : tipo === "etiqueta" ? cor.marcaEtiqueta : cor.fundoSuperficie;
  const texto = tipo === "primario" ? cor.textoInverso : tipo === "etiqueta" ? cor.marcaSobreEtiqueta : cor.textoPrincipal;
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
        { backgroundColor: fundo },
        tipo === "contorno" && { borderWidth: 1.5, borderColor: cor.bordaPadrao },
        largo && estilos.largo,
        pressed && { opacity: 0.92 },
        desativado && { opacity: 0.4 },
      ]}
    >
      {ocupado ? <ActivityIndicator color={texto} /> : <Text style={[fonte("botao"), { color: texto }]}>{rotulo}</Text>}
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  botao: { height: 52, borderRadius: 26, paddingHorizontal: 24, alignItems: "center", justifyContent: "center" },
  largo: { alignSelf: "stretch" },
});
