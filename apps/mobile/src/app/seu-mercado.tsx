/** R10 Seu mercado: onde a casa costuma comprar. Os preços do app começam por ele; vale para a família toda. */
import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Mercado } from "@/api/cliente";
import { MarcaDaRede } from "@/componentes/MarcaDaRede";
import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { km } from "@/formatar";
import { escolherMercado, useMercados } from "@/lista/mercado";
import { fonte, useTema } from "@/tema";

const TIPO: Record<Mercado["tipo_preco"], string> = {
  site: "Preço do site, conferido todo dia",
  encarte: "Só as ofertas do encarte",
  sem: "Ainda sem preço: em breve, pelos cupons que vocês lerem",
};

export default function SeuMercado() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const m = useMercados();
  const [salvando, setSalvando] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function escolher(lojaId: string | null) {
    setSalvando(lojaId ?? "auto");
    setErro(null);
    try {
      await escolherMercado(lojaId);
    } catch {
      setErro("Sem internet agora. Tente de novo em instantes.");
    } finally {
      setSalvando(null);
    }
  }

  const comPreco = (m?.lojas ?? []).filter((l) => l.tipo_preco !== "sem").slice(0, 10);
  const semPreco = (m?.lojas ?? []).filter((l) => l.tipo_preco === "sem").slice(0, 3);

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8 }]}>
      <View style={estilos.topo}>
        <Pressable accessibilityRole="button" accessibilityLabel="Fechar" hitSlop={8} onPress={() => router.back()} style={estilos.voltar}>
          <Icone nome="fechar" cor={cor.textoPrincipal} />
        </Pressable>
        <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
          Seu mercado
        </Text>
      </View>
      <ScrollView contentContainerStyle={[estilos.conteudo, { paddingBottom: margem.bottom + 24 }]}>
        <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
          É onde a casa costuma comprar. Os preços do app começam por ele; outro mercado só aparece quando compensa a viagem.
        </Text>
        {!m ? <ActivityIndicator color={cor.estadoEconomia} /> : null}
        <View style={[estilos.caixa, { borderColor: cor.bordaPadrao }]}>
          {comPreco.map((l, i) => {
            const marcado = m?.seu_mercado?.loja_id === l.loja_id && !m.automatico;
            const automatico = m?.automatico && m.seu_mercado?.loja_id === l.loja_id;
            return (
              <Pressable
                key={l.loja_id}
                accessibilityRole="radio"
                accessibilityState={{ checked: marcado }}
                accessibilityLabel={`${l.nome}, ${km(l.distancia_km)}. ${TIPO[l.tipo_preco]}`}
                onPress={() => void escolher(l.loja_id)}
                style={[estilos.linha, i > 0 && { borderTopWidth: 1, borderColor: cor.bordaPadrao }]}
              >
                <View style={[estilos.radio, marcado ? { backgroundColor: cor.estadoEconomia } : { borderColor: cor.bordaForte, borderWidth: 1.5 }]}>
                  {marcado ? <Icone nome="ok" cor={cor.textoInverso} tamanho={16} /> : null}
                </View>
                <MarcaDaRede rede={l.rede} tamanho={32} />
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{l.nome}</Text>
                  <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
                    {TIPO[l.tipo_preco]}
                    {automatico ? " · o mais perto (automático)" : ""}
                  </Text>
                </View>
                {salvando === l.loja_id ? (
                  <ActivityIndicator color={cor.estadoEconomia} />
                ) : (
                  <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{km(l.distancia_km)}</Text>
                )}
              </Pressable>
            );
          })}
        </View>
        {semPreco.length ? (
          <>
            <Text style={[fonte("rotulo"), { color: cor.textoSuave }]}>Perto, ainda sem preço</Text>
            <View style={[estilos.caixa, { borderColor: cor.bordaPadrao, opacity: 0.7 }]}>
              {semPreco.map((l, i) => (
                <View key={l.loja_id} style={[estilos.linha, i > 0 && { borderTopWidth: 1, borderColor: cor.bordaPadrao }]}>
                  <MarcaDaRede rede={l.rede} tamanho={32} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{l.nome}</Text>
                    <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{TIPO.sem}</Text>
                  </View>
                  <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{km(l.distancia_km)}</Text>
                </View>
              ))}
            </View>
          </>
        ) : null}
        <View style={estilos.linha}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>Escolher sempre o mais perto</Text>
            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Se a casa mudar de bairro, o app troca sozinho</Text>
          </View>
          <Switch
            accessibilityLabel="Escolher sempre o mais perto"
            value={!!m?.automatico}
            onValueChange={(v) => void escolher(v ? null : (m?.seu_mercado?.loja_id ?? null))}
            trackColor={{ true: cor.estadoEconomia, false: cor.bordaForte }}
            thumbColor={cor.fundoSuperficie}
          />
        </View>
        {erro ? <Text style={[fonte("corpoMenor"), { color: cor.estadoAlerta }]}>{erro}</Text> : null}
        <Botao rotulo="Pronto" aoTocar={() => router.back()} largo />
      </ScrollView>
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  topo: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingBottom: 8 },
  voltar: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  conteudo: { paddingHorizontal: 20, gap: 16 },
  caixa: { borderWidth: 1, borderRadius: 14, overflow: "hidden" },
  linha: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 14, paddingHorizontal: 16 },
  radio: { width: 22, height: 22, borderRadius: 11, alignItems: "center", justifyContent: "center" },
});
