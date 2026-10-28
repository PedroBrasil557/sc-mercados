import { useState } from "react";
import { Alert, Share, StyleSheet, Text, View } from "react-native";

import { api } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { StatusDoServidor } from "@/componentes/StatusDoServidor";
import { TelaProvisoria } from "@/componentes/TelaProvisoria";
import { useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Perfil() {
  const { sessao } = useLista();
  const { cor, medida } = useTema();
  const [convite, setConvite] = useState<{ codigo: string; expira_em: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  async function convidar() {
    setOcupado(true);
    try {
      const c = await api.convidar();
      setConvite(c);
      await Share.share({
        message: `Entra na lista da nossa casa no SC Mercados: abra o app, toque em "Entrar na casa" e use o código ${c.codigo} (vale por 48 horas).`,
      });
    } catch (e) {
      Alert.alert("Não deu para gerar o convite", e instanceof Error ? e.message : "Verifique a internet e tente de novo.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <TelaProvisoria titulo="Perfil" descricao="Casa, bairro, quem participa da lista, privacidade e exclusão de conta.">
      <StatusDoServidor />
      {sessao ? (
        <View style={[estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderRadius: medida.raioMedio }]}>
          <Text style={[fonte("rotulo"), { color: cor.textoSuave }]}>Sua casa</Text>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoPrincipal }]}>{Object.values(sessao.nomes).sort().join(", ")}</Text>
          <Botao rotulo="Convidar alguém da casa" aoTocar={() => void convidar()} ocupado={ocupado} />
          {convite ? (
            <Text selectable accessibilityLiveRegion="polite" style={[fonte("seloDeFonte"), { color: cor.textoPrincipal }]}>
              Código: {convite.codigo} · vale até {new Date(convite.expira_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}
            </Text>
          ) : null}
        </View>
      ) : null}
    </TelaProvisoria>
  );
}

const estilos = StyleSheet.create({
  cartao: { borderWidth: StyleSheet.hairlineWidth, padding: 16, gap: 10 },
});
