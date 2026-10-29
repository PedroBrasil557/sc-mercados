/** 10 Cupom lido: a economia da compra, com a base do cálculo à vista (R12). */
import { router, useLocalSearchParams } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { CupomLido as Resultado } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { reais } from "@/formatar";
import { fonte, useTema } from "@/tema";

export default function CupomLido() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const params = useLocalSearchParams<{ resultado: string; data: string }>();
  const r = JSON.parse(params.resultado ?? "{}") as Resultado;
  const e = r.economia;
  const linha = (rotulo: string, valor: string, destaque = false) => (
    <View style={estilos.linha}>
      <Text style={[fonte("cupomLinha"), { color: cor.textoPrincipal, flex: 1 }]}>{rotulo}</Text>
      <Text style={[fonte("cupomLinha"), { color: destaque ? cor.estadoEconomia : cor.textoPrincipal }]}>{valor}</Text>
    </View>
  );

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 32, paddingBottom: margem.bottom + 16 }]}>
      <View style={estilos.topo}>
        <View style={[estilos.circulo, { backgroundColor: cor.estadoEconomiaSuave }]}>
          <Icone nome="brilho" cor={cor.estadoEconomia} tamanho={32} />
        </View>
        {e && e.economia_centavos > 0 ? (
          <>
            <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Você economizou</Text>
            <Text accessibilityRole="header" style={[fonte("displayGrande"), { color: cor.estadoEconomia }]}>
              {reais(e.economia_centavos)}
            </Text>
            <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, textAlign: "center" }]}>nesta compra, {e.base}</Text>
          </>
        ) : (
          <>
            <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal, textAlign: "center" }]}>
              Cupom guardado
            </Text>
            <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, textAlign: "center" }]}>
              {e
                ? "Nos itens que reconhecemos, você pagou o mesmo que a média dos outros mercados."
                : "Ainda estamos reconhecendo os itens deste mercado. A economia aparece aqui nas próximas compras."}
            </Text>
          </>
        )}
      </View>

      <View style={[estilos.recibo, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
        {linha((r.loja ?? "Mercado").toUpperCase(), params.data?.split("-").reverse().slice(0, 2).join("/") ?? "")}
        <View style={[estilos.tracejado, { borderColor: cor.bordaPadrao }]} />
        {linha(`${r.itens_reconhecidos} de ${r.itens} itens reconhecidos`, e ? reais(e.pago_centavos) : "—")}
        {e ? linha("Média dos outros mercados", reais(e.media_centavos)) : null}
        {e ? linha("Economia", reais(e.economia_centavos), true) : null}
        {linha("Total do cupom", reais(r.total_centavos))}
        <View style={[estilos.tracejado, { borderColor: cor.bordaPadrao }]} />
        {linha("CPF do cupom", "não lido pelo app", true)}
      </View>
      <Text style={[fonte("legenda"), { color: cor.textoSuave, textAlign: "center", paddingHorizontal: 32 }]}>
        Seus cupons ajudam a manter o app certo para todo mundo, inclusive nos atacarejos sem site.
      </Text>

      <View style={{ flex: 1 }} />
      <View style={{ paddingHorizontal: 20 }}>
        <Botao rotulo="Salvar e voltar ao início" largo aoTocar={() => router.dismissTo("/")} />
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1, gap: 16 },
  topo: { alignItems: "center", gap: 6, paddingHorizontal: 24 },
  circulo: { width: 64, height: 64, borderRadius: 32, alignItems: "center", justifyContent: "center", marginBottom: 8 },
  recibo: { marginHorizontal: 20, borderRadius: 12, borderWidth: 1, padding: 16, gap: 8 },
  linha: { flexDirection: "row", gap: 12 },
  tracejado: { borderTopWidth: 1, borderStyle: "dashed" },
});
