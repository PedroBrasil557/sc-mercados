/** Seus dados (LGPD) e Sobre: o que guardamos, onde, de onde vêm os dados e a exclusão da conta. */
import Constants from "expo-constants";
import { router } from "expo-router";
import { type ReactNode, useState } from "react";
import { Alert, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { API } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { apagarMinhaConta } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Dados() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const [apagando, setApagando] = useState(false);

  function confirmarExclusao() {
    Alert.alert(
      "Apagar seus dados?",
      "Seu nome e o seu acesso à lista saem dos nossos servidores agora. Se você for a última pessoa da casa, a lista também é apagada. Não dá para desfazer.",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Apagar",
          style: "destructive",
          onPress: () => {
            setApagando(true);
            apagarMinhaConta()
              .then(() => router.replace("/boas-vindas"))
              .catch(() => Alert.alert("Sem internet", "A exclusão precisa de conexão. Tente de novo em instantes."))
              .finally(() => setApagando(false));
          },
        },
      ],
    );
  }

  return (
    <ScrollView style={{ backgroundColor: cor.fundoTela }} contentContainerStyle={[estilos.conteudo, { paddingTop: margem.top + 8, paddingBottom: margem.bottom + 32 }]}>
      <Pressable accessibilityRole="button" accessibilityLabel="Voltar" hitSlop={8} onPress={() => router.back()} style={estilos.voltar}>
        <Icone nome="voltar" cor={cor.textoPrincipal} />
      </Pressable>
      <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
        Seus dados
      </Text>

      <Bloco titulo="O que guardamos">
        Seu nome (ou apelido), o bairro da casa e os itens da lista, com quem pôs cada um. Só o necessário para a lista da casa
        funcionar em todos os celulares.
      </Bloco>
      <Bloco titulo="O que nunca guardamos">
        CPF, sua localização, seus contatos e fotos. O app não pede cadastro com e-mail nem senha.
      </Bloco>
      <Bloco titulo="Onde ficam">
        Em servidores nos Estados Unidos (Supabase e Render), com acesso só pelo app. A lista também fica no seu celular para funcionar
        sem internet.
      </Bloco>
      <Bloco titulo="De onde vêm os preços">
        Dos sites das próprias redes (Giassi, Cooper, Angeloni, Sam’s Club e Rede Top), conferidos todo dia, dos encartes do Fort Atacadista e do Komprão e dos cupons fiscais lidos no app (só o preço dos produtos, nunca quem comprou).
        Cada preço mostra de onde veio e quando. Não recebemos dinheiro de nenhum mercado.
      </Bloco>
      <Bloco titulo="Sobre as imagens">
        Os produtos aparecem sem foto porque as fotos têm dono: só vamos usar imagens com licença. Por enquanto, cada produto mostra a
        categoria e o tamanho.
      </Bloco>
      <Bloco titulo="Mapas e bairros">© colaboradores do OpenStreetMap (licença ODbL), para os bairros e as lojas sem site.</Bloco>

      <View style={estilos.links}>
        <Text accessibilityRole="link" onPress={() => Linking.openURL(`${API}/privacidade`)} style={[fonte("corpoForte"), { color: cor.estadoEconomia }]}>
          Política de privacidade
        </Text>
        <Text accessibilityRole="link" onPress={() => Linking.openURL(`${API}/termos`)} style={[fonte("corpoForte"), { color: cor.estadoEconomia }]}>
          Termos de uso
        </Text>
      </View>

      <View style={{ gap: 8, marginTop: 8 }}>
        <Botao rotulo="Apagar meus dados" tipo="contorno" largo ocupado={apagando} aoTocar={confirmarExclusao} />
        <Text style={[fonte("legenda"), { color: cor.textoSuave, textAlign: "center" }]}>
          SC Mercados {Constants.expoConfig?.version ?? ""}
        </Text>
      </View>
    </ScrollView>
  );
}

function Bloco({ titulo, children }: { titulo: string; children: ReactNode }) {
  const { cor } = useTema();
  return (
    <View style={estilos.bloco}>
      <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>{titulo}</Text>
      <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>{children}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  links: { flexDirection: "row", gap: 20, flexWrap: "wrap" },
  conteudo: { paddingHorizontal: 20, gap: 20 },
  voltar: { width: 44, height: 44, alignItems: "center", justifyContent: "center", marginLeft: -10 },
  bloco: { gap: 4 },
});
