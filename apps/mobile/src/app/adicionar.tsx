/** 04 Adicionar item: busca no catálogo, com o menor preço de hoje em cada resultado. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Produto } from "@/api/cliente";
import { Icone } from "@/componentes/Icone";
import { Miniatura } from "@/componentes/Miniatura";
import { reais, tamanho } from "@/formatar";
import { adicionarProduto, buscarProdutos, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Adicionar() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const params = useLocalSearchParams<{ busca?: string }>();
  const { itens } = useLista();
  const [busca, setBusca] = useState(params.busca ?? "");
  const [resultado, setResultado] = useState<{ produtos: Produto[]; semConexao: boolean } | null>(null);

  useEffect(() => {
    let valido = true;
    const espera = setTimeout(() => void buscarProdutos(busca.trim()).then((r) => valido && setResultado(r)), 200);
    return () => {
      valido = false;
      clearTimeout(espera);
    };
  }, [busca]);

  const naLista = (p: Produto) => itens.find((i) => i.produto_id === p.id && !i.comprado);

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8 }]}>
      <View style={estilos.topo}>
        <Pressable accessibilityRole="button" accessibilityLabel="Voltar para a lista" hitSlop={8} onPress={() => router.back()} style={estilos.voltar}>
          <Icone nome="voltar" cor={cor.textoPrincipal} />
        </Pressable>
        <View style={[estilos.busca, { backgroundColor: cor.fundoSuperficie, borderColor: cor.estadoEconomia }]}>
          <Icone nome="buscar" cor={cor.textoSuave} />
          <TextInput
            autoFocus
            accessibilityLabel="Buscar produto"
            placeholder="O que está faltando em casa?"
            placeholderTextColor={cor.textoSuave}
            selectionColor={cor.estadoEconomia}
            value={busca}
            onChangeText={setBusca}
            returnKeyType="search"
            style={[fonte("corpoForte"), estilos.campo, { color: cor.textoPrincipal }]}
          />
        </View>
      </View>

      <FlatList
        data={resultado?.produtos ?? []}
        keyExtractor={(p) => p.id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={estilos.lista}
        ListHeaderComponent={
          resultado?.semConexao ? (
            <Text style={[fonte("legenda"), { color: cor.textoSuave, paddingBottom: 8 }]}>
              Sem internet: buscando no catálogo guardado no celular, sem os preços de hoje.
            </Text>
          ) : undefined
        }
        ListEmptyComponent={
          resultado ? (
            <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, paddingTop: 16 }]}>
              {busca.trim() ? `Ainda não temos “${busca.trim()}” no catálogo.` : "Busque pelo nome ou pela marca."}
            </Text>
          ) : undefined
        }
        renderItem={({ item }) => {
          const ja = naLista(item);
          const detalhe = [
            item.marca,
            item.menor_preco_centavos ? `a partir de ${reais(item.menor_preco_centavos)} no ${item.menor_preco_rede}` : null,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <View style={estilos.resultado}>
              <Miniatura categoria={item.categoria} tamanho={tamanho(item.tamanho, item.unidade)} nome={item.nome} />
              <View style={{ flex: 1, gap: 2 }}>
                <Text numberOfLines={2} style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>
                  {item.nome}
                </Text>
                {ja ? (
                  <Text style={[fonte("legenda"), { color: cor.estadoEconomia }]}>Na lista · {ja.quantidade}</Text>
                ) : detalhe ? (
                  <Text numberOfLines={2} style={[fonte("legenda"), { color: cor.textoSuave }]}>
                    {detalhe}
                  </Text>
                ) : null}
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={ja ? `Somar mais um ${item.nome}` : `Pôr ${item.nome} na lista`}
                onPress={() => adicionarProduto(item)}
                style={({ pressed }) => [estilos.mais, { backgroundColor: cor.fundoProfundo }, pressed && { opacity: 0.85 }]}
              >
                <Icone nome="mais" cor={cor.textoInverso} />
              </Pressable>
            </View>
          );
        }}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  topo: { flexDirection: "row", alignItems: "center", gap: 8, paddingLeft: 12, paddingRight: 20, paddingBottom: 12 },
  voltar: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  busca: { flex: 1, height: 54, borderRadius: 27, borderWidth: 1.5, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16 },
  campo: { flex: 1, paddingVertical: 0 },
  lista: { paddingHorizontal: 20, paddingBottom: 40 },
  resultado: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12 },
  mais: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
});
