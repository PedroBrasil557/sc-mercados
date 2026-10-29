/** 12 Convidar: painel para chamar alguém da casa pelo WhatsApp. */
import * as Clipboard from "expo-clipboard";
import { useEffect, useState } from "react";
import { ActivityIndicator, Linking, Modal, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/api/cliente";
import { trocarApelido, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Campo } from "./Campo";
import { Icone } from "./Icone";

export function ConvidarCasa({ visivel, aoFechar }: { visivel: boolean; aoFechar: () => void }) {
  return (
    <Modal visible={visivel} transparent animationType="slide" onRequestClose={aoFechar} statusBarTranslucent navigationBarTranslucent>
      {visivel ? <Painel aoFechar={aoFechar} /> : null}
    </Modal>
  );
}

function Painel({ aoFechar }: { aoFechar: () => void }) {
  const { cor, medida } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao } = useLista();
  const [convite, setConvite] = useState<{ codigo: string } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  // Quem ainda é "Eu" escolhe um nome antes: é ele que a família vê nos itens ("Pedro, agora").
  const [nome, setNome] = useState(sessao?.apelido === "Eu" ? "" : (sessao?.apelido ?? ""));
  const precisaNome = sessao?.apelido === "Eu";

  useEffect(() => {
    let valido = true;
    api
      .convidar()
      .then((c) => valido && setConvite(c))
      .catch(() => valido && setErro("Sem internet: o convite precisa de conexão."));
    return () => {
      valido = false;
    };
  }, []);

  const mensagem = (codigo: string) =>
    `Entra na lista da nossa casa no SC Mercados! Abra o app, toque em "Recebi um convite da minha casa" e use o código ${codigo}. Vale por 48 horas.`;

  async function enviar() {
    if (!convite) return;
    if (precisaNome && nome.trim()) await trocarApelido(nome).catch(() => undefined);
    const whatsapp = `whatsapp://send?text=${encodeURIComponent(mensagem(convite.codigo))}`;
    if (await Linking.canOpenURL(whatsapp).catch(() => false)) await Linking.openURL(whatsapp);
    else await Share.share({ message: mensagem(convite.codigo) });
    aoFechar();
  }

  return (
    <>
      <Pressable accessibilityLabel="Fechar" style={[StyleSheet.absoluteFill, { backgroundColor: cor.sobreposicaoVeu }]} onPress={aoFechar} />
      <View
        style={[
          estilos.painel,
          { backgroundColor: cor.fundoSuperficie, borderTopLeftRadius: medida.raioTela, borderTopRightRadius: medida.raioTela, paddingBottom: margem.bottom + 16 },
        ]}
      >
        <View style={[estilos.alca, { backgroundColor: cor.bordaPadrao }]} />
        <View style={[estilos.icone, { backgroundColor: cor.estadoEconomiaSuave }]}>
          <Icone nome="familia" cor={cor.estadoEconomia} tamanho={32} />
        </View>
        <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal, textAlign: "center" }]}>
          Convide a sua casa
        </Text>
        <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>
          Quem usar o código entra na mesma lista e pode somar, tirar e marcar itens, mesmo sem internet.
        </Text>
        {precisaNome ? (
          <Campo rotulo="Seu nome" placeholder="Seu nome (a família vê nos itens)" value={nome} onChangeText={setNome} maxLength={40} />
        ) : null}
        <View style={[estilos.codigo, { backgroundColor: cor.fundoAfundado }]}>
          {convite ? (
            <Text selectable style={[fonte("cupomLinha"), { color: cor.textoPrincipal, flex: 1, fontSize: 16, lineHeight: 22 }]}>
              Código: {convite.codigo}
            </Text>
          ) : erro ? (
            <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, flex: 1 }]}>{erro}</Text>
          ) : (
            <ActivityIndicator color={cor.estadoEconomia} style={{ flex: 1 }} />
          )}
          {convite ? (
            <Pressable
              accessibilityRole="button"
              hitSlop={8}
              onPress={() => void Clipboard.setStringAsync(convite.codigo).then(() => setCopiado(true))}
              style={estilos.copiar}
            >
              <Text style={[fonte("corpoForte"), { color: cor.estadoEconomia }]}>{copiado ? "Copiado" : "Copiar"}</Text>
            </Pressable>
          ) : null}
        </View>
        <Botao rotulo="Enviar pelo WhatsApp" largo desativado={!convite || (precisaNome && !nome.trim())} aoTocar={() => void enviar()} />
        <Pressable accessibilityRole="button" onPress={aoFechar} style={estilos.agoraNao}>
          <Text style={[fonte("botao"), { color: cor.textoPrincipal }]}>Agora não</Text>
        </Pressable>
      </View>
    </>
  );
}

const estilos = StyleSheet.create({
  painel: { position: "absolute", left: 0, right: 0, bottom: 0, paddingTop: 12, paddingHorizontal: 24, gap: 16, alignItems: "stretch" },
  alca: { alignSelf: "center", width: 40, height: 5, borderRadius: 3 },
  icone: { alignSelf: "center", width: 56, height: 56, borderRadius: 28, alignItems: "center", justifyContent: "center" },
  codigo: { flexDirection: "row", alignItems: "center", minHeight: 52, paddingHorizontal: 16, borderRadius: 14 },
  copiar: { minHeight: 44, justifyContent: "center", paddingLeft: 12 },
  agoraNao: { alignSelf: "center", minHeight: 48, justifyContent: "center", paddingHorizontal: 16 },
});
