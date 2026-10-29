/**
 * 07 Ofertas: só ofertas reais (R9), conferidas pelo histórico de preços.
 * A coleta diária começou em 28/10/2026; a tela completa entra na fase 2, com o histórico já acumulado.
 */
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { fonte, useTema } from "@/tema";

export default function Ofertas() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 4 }]}>
      <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
        Ofertas
      </Text>
      <View style={estilos.centro}>
        <View style={[estilos.circulo, { backgroundColor: cor.marcaEtiqueta }]}>
          <Icone nome="oferta" cor={cor.marcaSobreEtiqueta} tamanho={40} />
        </View>
        <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal, textAlign: "center" }]}>Só ofertas de verdade</Text>
        <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>
          Uma oferta só aparece aqui quando o preço está mesmo abaixo do que o mercado costuma cobrar. Para saber isso, o app
          acompanha os preços todos os dias desde 28 de outubro. As primeiras ofertas conferidas chegam nas próximas semanas.
        </Text>
        <Botao rotulo="Comparar a minha lista" tipo="contorno" aoTocar={() => router.navigate("/comparar")} />
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1, paddingHorizontal: 20 },
  centro: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, paddingBottom: 48 },
  circulo: { width: 96, height: 96, borderRadius: 48, alignItems: "center", justifyContent: "center", marginBottom: 8 },
});
