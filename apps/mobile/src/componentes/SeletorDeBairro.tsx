/** 22 Trocar bairro: painel de baixo com busca e a lista de bairros da cidade. */
import { useEffect, useMemo, useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Bairro } from "@/api/cliente";
import * as armazem from "@/lista/armazem";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Icone } from "./Icone";

const semAcento = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Bairros da API, guardados no aparelho para abrir sem internet. */
export function useBairros(): Bairro[] {
  const [bairros, setBairros] = useState<Bairro[]>(() => armazem.lerGuardado<Bairro[]>("bairros") ?? []);
  useEffect(() => {
    api
      .bairros()
      .then((b) => {
        armazem.guardar("bairros", b);
        setBairros(b);
      })
      .catch(() => undefined);
  }, []);
  return bairros;
}

type Props = {
  visivel: boolean;
  selecionado: string | null;
  aoFechar: () => void;
  aoConfirmar: (bairro: Bairro) => void;
};

export function SeletorDeBairro(props: Props) {
  return (
    <Modal visible={props.visivel} transparent animationType="slide" onRequestClose={props.aoFechar} statusBarTranslucent navigationBarTranslucent>
      {/* Montado a cada abertura: começa sempre no bairro atual, sem busca. */}
      {props.visivel ? <Painel {...props} /> : null}
    </Modal>
  );
}

function Painel({ selecionado, aoFechar, aoConfirmar }: Props) {
  const { cor, medida } = useTema();
  const margem = useSafeAreaInsets();
  const bairros = useBairros();
  const [busca, setBusca] = useState("");
  const [escolhido, setEscolhido] = useState<string | null>(selecionado);

  const filtrados = useMemo(() => {
    const termo = semAcento(busca.trim());
    const lista = termo ? bairros.filter((b) => semAcento(b.nome).includes(termo)) : bairros;
    // O escolhido aparece primeiro, como no Figma.
    return [...lista].sort((a, b) => Number(b.id === escolhido) - Number(a.id === escolhido));
  }, [bairros, busca, escolhido]);

  const bairro = bairros.find((b) => b.id === escolhido) ?? null;

  return (
    <>
      <Pressable accessibilityLabel="Fechar" style={[StyleSheet.absoluteFill, { backgroundColor: cor.sobreposicaoVeu }]} onPress={aoFechar} />
      <View
        style={[
          estilos.painel,
          { backgroundColor: cor.fundoSuperficie, borderTopLeftRadius: medida.raioTela, borderTopRightRadius: medida.raioTela, paddingBottom: margem.bottom + 24 },
        ]}
      >
        <View style={[estilos.alca, { backgroundColor: cor.bordaPadrao }]} />
        <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
          Onde você mora?
        </Text>
        <View style={[estilos.busca, { borderColor: cor.bordaForte }]}>
          <Icone nome="buscar" cor={cor.textoSuave} />
          <TextInput
            accessibilityLabel="Buscar bairro"
            placeholder="Buscar bairro"
            placeholderTextColor={cor.textoSuave}
            value={busca}
            onChangeText={setBusca}
            style={[fonte("corpoPadrao"), estilos.campo, { color: cor.textoPrincipal }]}
          />
        </View>
        <FlatList
          data={filtrados}
          keyExtractor={(b) => b.id}
          keyboardShouldPersistTaps="handled"
          style={estilos.lista}
          ListEmptyComponent={
            <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, paddingVertical: 12 }]}>
              {bairros.length ? "Nenhum bairro com esse nome." : "Carregando os bairros…"}
            </Text>
          }
          renderItem={({ item }) => {
            const ativo = item.id === escolhido;
            return (
              <Pressable
                accessibilityRole="radio"
                accessibilityState={{ checked: ativo }}
                onPress={() => setEscolhido(item.id)}
                style={[estilos.bairro, { borderBottomColor: cor.bordaPadrao }]}
              >
                <Text style={[fonte(ativo ? "corpoForte" : "corpoPadrao"), { color: cor.textoPrincipal, flex: 1 }]}>{item.nome}</Text>
                {ativo ? (
                  <View style={[estilos.marcado, { backgroundColor: cor.estadoEconomia }]}>
                    <Icone nome="ok" cor={cor.textoInverso} tamanho={20} />
                  </View>
                ) : null}
              </Pressable>
            );
          }}
        />
        <Botao rotulo="Confirmar" largo desativado={!bairro} aoTocar={() => bairro && aoConfirmar(bairro)} />
      </View>
    </>
  );
}

const estilos = StyleSheet.create({
  painel: { position: "absolute", left: 0, right: 0, bottom: 0, maxHeight: "86%", paddingTop: 12, paddingHorizontal: 24, gap: 16 },
  alca: { alignSelf: "center", width: 40, height: 5, borderRadius: 3 },
  busca: { height: 54, borderRadius: 27, borderWidth: 1.5, flexDirection: "row", alignItems: "center", gap: 12, paddingLeft: 16, paddingRight: 8 },
  campo: { flex: 1, paddingVertical: 0 },
  lista: { flexGrow: 0 },
  bairro: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 48, paddingVertical: 12, borderBottomWidth: 1 },
  marcado: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
});
