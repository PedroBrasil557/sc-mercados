/** 01 Boas-vindas: a primeira abertura. Escolhe o bairro e começa, sem cadastro. */
import { router } from "expo-router";
import { useState } from "react";
import { Alert, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Bairro } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Campo } from "@/componentes/Campo";
import { Icone } from "@/componentes/Icone";
import { SeletorDeBairro } from "@/componentes/SeletorDeBairro";
import { comecarCasa, entrarComConvite, recuperarConta } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

const ILUSTRACAO = require("../../assets/ilustracoes/boas-vindas.webp");

export default function BoasVindas() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const [bairro, setBairro] = useState<Bairro | null>(null);
  const [escolhendo, setEscolhendo] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [convite, setConvite] = useState<{ codigo: string; apelido: string } | null>(null);
  const [recuperacao, setRecuperacao] = useState<string | null>(null);

  async function comecar() {
    if (!bairro) return setEscolhendo(true);
    setOcupado(true);
    try {
      await comecarCasa(bairro);
      router.replace("/");
    } catch (e) {
      Alert.alert("Não deu para começar agora", e instanceof Error ? e.message : "Verifique a internet e tente de novo.");
    } finally {
      setOcupado(false);
    }
  }

  async function recuperar() {
    if (!recuperacao?.trim()) return;
    setOcupado(true);
    try {
      await recuperarConta(recuperacao);
      router.replace("/lista");
    } catch (e) {
      Alert.alert("Não deu para recuperar", e instanceof Error ? e.message : "Confira o código e tente de novo.");
    } finally {
      setOcupado(false);
    }
  }

  async function entrar() {
    if (!convite?.codigo.trim() || !convite.apelido.trim()) {
      return Alert.alert("Faltou um dado", "Escreva o código que recebeu e como você quer ser chamado.");
    }
    setOcupado(true);
    try {
      await entrarComConvite(convite.codigo, convite.apelido);
      router.replace("/lista");
    } catch (e) {
      Alert.alert("Não deu para entrar na casa", e instanceof Error ? e.message : "Confira o código e tente de novo.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela }]}>
      <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
        <Image source={ILUSTRACAO} resizeMode="cover" accessibilityIgnoresInvertColors style={estilos.ilustracao} />
        <View style={estilos.conteudo}>
          <Text style={[fonte("rotulo"), { color: cor.estadoEconomia }]}>Blumenau · SC</Text>
          <Text accessibilityRole="header" style={[fonte("displayGrande"), { color: cor.textoPrincipal }]}>
            Quanto fica a sua lista em cada mercado?
          </Text>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
            Compare Giassi, Cooper, Angeloni e outros antes de sair de casa. Sem cadastro.
          </Text>

          {recuperacao !== null ? (
            <View style={{ gap: 12 }}>
              <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Recuperar minha lista num celular novo</Text>
              <Campo
                rotulo="Código de recuperação"
                placeholder="XXXX-XXXX-XXXX"
                autoCapitalize="characters"
                autoCorrect={false}
                maxLength={20}
                value={recuperacao}
                onChangeText={setRecuperacao}
              />
            </View>
          ) : convite ? (
            <View style={{ gap: 12 }}>
              <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Entrar na lista de uma casa</Text>
              <Campo
                rotulo="Código do convite"
                placeholder="Código de 8 letras"
                autoCapitalize="characters"
                autoCorrect={false}
                maxLength={10}
                value={convite.codigo}
                onChangeText={(codigo) => setConvite({ ...convite, codigo })}
              />
              <Campo
                rotulo="Seu apelido"
                placeholder="Como a família te chama?"
                maxLength={40}
                value={convite.apelido}
                onChangeText={(apelido) => setConvite({ ...convite, apelido })}
              />
            </View>
          ) : (
            <View style={{ gap: 8 }}>
              <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Onde você mora?</Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={bairro ? `Bairro: ${bairro.nome}. Toque para trocar` : "Escolher o bairro"}
                onPress={() => setEscolhendo(true)}
                style={[estilos.seletor, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaForte }]}
              >
                <Icone nome="local" cor={cor.estadoEconomia} />
                <Text style={[fonte("corpoForte"), { color: bairro ? cor.textoPrincipal : cor.textoSuave, flex: 1 }]}>
                  {bairro?.nome ?? "Escolha o seu bairro"}
                </Text>
                <View style={{ transform: [{ rotate: "90deg" }] }}>
                  <Icone nome="seta-direita" cor={cor.textoPrincipal} tamanho={20} />
                </View>
              </Pressable>
            </View>
          )}
        </View>
      </ScrollView>

      <View style={[estilos.rodape, { paddingBottom: margem.bottom + 20 }]}>
        {recuperacao !== null ? (
          <>
            <Botao rotulo="Recuperar minha lista" largo ocupado={ocupado} aoTocar={() => void recuperar()} />
            <Pressable accessibilityRole="button" onPress={() => setRecuperacao(null)} style={estilos.link}>
              <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>Voltar</Text>
            </Pressable>
          </>
        ) : convite ? (
          <>
            <Botao rotulo="Entrar na casa" largo ocupado={ocupado} aoTocar={() => void entrar()} />
            <Pressable accessibilityRole="button" onPress={() => setConvite(null)} style={estilos.link}>
              <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>Voltar e começar uma lista nova</Text>
            </Pressable>
          </>
        ) : (
          <>
            <Botao rotulo="Ver os mercados perto de mim" largo ocupado={ocupado} aoTocar={() => void comecar()} />
            <View style={estilos.links}>
              <Pressable accessibilityRole="button" onPress={() => setConvite({ codigo: "", apelido: "" })} style={estilos.link}>
                <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>Recebi um convite</Text>
              </Pressable>
              <Pressable accessibilityRole="button" onPress={() => setRecuperacao("")} style={estilos.link}>
                <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>Trocar de celular</Text>
              </Pressable>
            </View>
            <Text style={[fonte("legenda"), { color: cor.textoSuave, textAlign: "center" }]}>
              Preço de prateleira, sem taxa de entrega. Cada preço mostra de onde veio.
            </Text>
          </>
        )}
      </View>

      <SeletorDeBairro
        visivel={escolhendo}
        selecionado={bairro?.id ?? null}
        aoFechar={() => setEscolhendo(false)}
        aoConfirmar={(b) => {
          setBairro(b);
          setEscolhendo(false);
        }}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  ilustracao: { width: "100%", height: 320, borderBottomLeftRadius: 32, borderBottomRightRadius: 32 },
  conteudo: { paddingTop: 28, paddingHorizontal: 24, gap: 16 },
  seletor: { height: 56, borderRadius: 16, borderWidth: 1.5, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16 },
  rodape: { paddingTop: 12, paddingHorizontal: 24, gap: 12, alignItems: "center" },
  link: { minHeight: 44, justifyContent: "center", paddingHorizontal: 8 },
  links: { flexDirection: "row", gap: 16 },
});
