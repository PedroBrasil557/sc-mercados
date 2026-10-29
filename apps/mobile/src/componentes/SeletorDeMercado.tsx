import { router } from "expo-router";
import { Pressable, StyleSheet, Text } from "react-native";

import { km } from "@/formatar";
import { useMercados } from "@/lista/mercado";
import { fonte, useTema } from "@/tema";

import { Icone } from "./Icone";

/** Figma "v2/Seletor de mercado": toda tela de preço começa pelo seu mercado. Toque troca o mercado. */
export function SeletorDeMercado() {
  const { cor } = useTema();
  const m = useMercados();
  const seu = m?.seu_mercado;
  const texto = seu ? `Seu mercado: ${seu.nome} · ${km(seu.distancia_km)}` : "Seu mercado: escolher";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${texto}. Trocar o seu mercado`}
      onPress={() => router.push("/seu-mercado")}
      style={({ pressed }) => [estilos.pilula, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }, pressed && { opacity: 0.8 }]}
    >
      <Icone nome="loja" cor={cor.estadoEconomia} tamanho={20} />
      <Text numberOfLines={1} style={[fonte("corpoMenor"), { color: cor.textoPrincipal, flexShrink: 1 }]}>
        {texto}
      </Text>
      <Icone nome="seta-direita" cor={cor.textoSuave} tamanho={16} />
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  pilula: { flexDirection: "row", alignItems: "center", gap: 8, alignSelf: "flex-start", maxWidth: "100%", borderWidth: 1, borderRadius: 16, paddingVertical: 8, paddingHorizontal: 12 },
});
