/** 03 Lista da casa (e 16 Lista vazia). A busca para adicionar abre a tela 04. */
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AvisoComDesfazer } from "@/componentes/AvisoComDesfazer";
import { Botao } from "@/componentes/Botao";
import { Chip } from "@/componentes/Chip";
import { Icone } from "@/componentes/Icone";
import { ItemDaLista } from "@/componentes/ItemDaLista";
import { quantidade, reais } from "@/formatar";
import { useComparacao } from "@/lista/comparacao";
import { alternarComprado, type ItemVisivel, remover, restaurar, somar, tirar, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

// Sugestões da lista vazia: só o que existe no catálogo (cada uma abre a busca já preenchida).
const COMECE_POR = ["Leite", "Arroz", "Café", "Feijão", "Açúcar", "Óleo"];

export default function Lista() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao, itens, situacao } = useLista();
  const { dados } = useComparacao();
  const [removido, setRemovido] = useState<ItemVisivel | null>(null);
  const sumirAviso = useCallback(() => setRemovido(null), []);

  const buscar = (termo = "") => router.push({ pathname: "/adicionar", params: termo ? { busca: termo } : {} });
  const pessoas = sessao ? Object.values(sessao.nomes).map((n) => (n === sessao.apelido ? "você" : n)) : [];
  const subtitulo = itens.length ? `${itens.length} ${itens.length === 1 ? "item" : "itens"} · ${juntar(pessoas)}` : "Nenhum item ainda";
  const maisBarata = dados?.lojas[0];

  async function compartilhar() {
    const linhas = itens.filter((i) => !i.comprado).map((i) => `• ${i.nome}${i.quantidade !== 1 ? ` (${quantidade(i.quantidade)})` : ""}`);
    await Share.share({ message: `Lista da casa no SC Mercados:\n${linhas.join("\n")}` });
  }

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 4 }]}>
      <View style={estilos.cabecalho}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
            Lista da casa
          </Text>
          <Text numberOfLines={1} style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
            {subtitulo}
          </Text>
        </View>
        {itens.length ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Compartilhar a lista"
            onPress={() => void compartilhar()}
            style={[estilos.circulo, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}
          >
            <Icone nome="compartilhar" cor={cor.textoPrincipal} tamanho={20} />
          </Pressable>
        ) : null}
      </View>

      <View style={estilos.margens}>
        <Pressable
          accessibilityRole="search"
          accessibilityLabel="Buscar produto para pôr na lista"
          onPress={() => buscar()}
          style={[estilos.busca, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaForte }]}
        >
          <Icone nome="buscar" cor={cor.textoSuave} />
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, flex: 1 }]}>O que está faltando em casa?</Text>
        </Pressable>
        {situacao.semConexao || situacao.pendentes ? (
          <View style={estilos.situacao}>
            <Icone nome={situacao.semConexao ? "sem-internet" : "relogio"} cor={cor.textoSuave} tamanho={16} />
            <Text style={[fonte("legenda"), { color: cor.textoSuave, flex: 1 }]}>
              {situacao.semConexao
                ? "Sem internet: suas mudanças ficam guardadas e vão para a casa quando a conexão voltar."
                : `${situacao.pendentes} ${situacao.pendentes === 1 ? "mudança" : "mudanças"} indo para a casa…`}
            </Text>
          </View>
        ) : null}
      </View>

      {itens.length ? (
        <FlatList
          data={itens}
          keyExtractor={(i) => i.id}
          contentContainerStyle={[estilos.margens, { paddingBottom: 120 }]}
          renderItem={({ item }) => (
            <ItemDaLista
              item={item}
              meuNome={sessao?.apelido ?? ""}
              aoSomar={() => somar(item.id)}
              aoTirar={() => {
                if (item.quantidade <= 1) setRemovido(item);
                tirar(item.id);
              }}
              aoTocar={() => alternarComprado(item)}
              aoSegurar={() => {
                setRemovido(item);
                remover(item.id);
              }}
            />
          )}
        />
      ) : (
        <View style={[estilos.margens, estilos.vazio]}>
          <View style={[estilos.ilustracao, { backgroundColor: cor.estadoEconomiaSuave }]}>
            <Icone nome="lista" cor={cor.estadoEconomia} tamanho={40} />
          </View>
          <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal, textAlign: "center" }]}>O que está faltando em casa?</Text>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>
            Anote aqui. O app mostra na hora quanto a lista custa em cada mercado perto de você.
          </Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, alignSelf: "flex-start", marginTop: 16 }]}>Comece por estes</Text>
          <View style={estilos.chips}>
            {COMECE_POR.map((s) => (
              <Chip key={s} texto={`+ ${s}`} aoTocar={() => buscar(s)} />
            ))}
          </View>
        </View>
      )}

      <View style={[estilos.rodape, { paddingBottom: 12 }]} pointerEvents="box-none">
        {removido ? (
          <AvisoComDesfazer
            texto={`${removido.nome} saiu da lista`}
            aoSumir={sumirAviso}
            aoDesfazer={() => {
              restaurar(removido.id, removido.quantidade);
              setRemovido(null);
            }}
          />
        ) : maisBarata && itens.some((i) => !i.comprado) ? (
          <View style={[estilos.resumo, { backgroundColor: cor.fundoProfundo }]}>
            <View style={{ flex: 1 }}>
              <Text style={[fonte("rotulo"), { color: cor.textoInverso }]}>Mais barato hoje</Text>
              <Text numberOfLines={1} style={[fonte("precoMedio"), { color: cor.textoInverso }]}>
                {reais(maisBarata.total_centavos)} · {maisBarata.rede}
              </Text>
            </View>
            <Botao rotulo="Comparar" tipo="etiqueta" aoTocar={() => router.navigate("/comparar")} />
          </View>
        ) : null}
      </View>
    </View>
  );
}

function juntar(nomes: string[]): string {
  if (nomes.length <= 1) return nomes[0] ?? "";
  return `${nomes.slice(0, -1).join(", ")} e ${nomes[nomes.length - 1]}`;
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  cabecalho: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 20, paddingBottom: 12 },
  circulo: { width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  margens: { paddingHorizontal: 20 },
  busca: { height: 54, borderRadius: 27, borderWidth: 1.5, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16 },
  situacao: { flexDirection: "row", alignItems: "center", gap: 6, paddingTop: 8 },
  vazio: { alignItems: "center", gap: 8, paddingTop: 48 },
  ilustracao: { width: 96, height: 96, borderRadius: 48, alignItems: "center", justifyContent: "center", marginBottom: 16 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, alignSelf: "stretch" },
  rodape: { position: "absolute", left: 20, right: 20, bottom: 0 },
  resumo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    minHeight: 68,
    paddingLeft: 20,
    paddingRight: 8,
    paddingVertical: 8,
    borderRadius: 22,
    shadowColor: "#0F241C",
    shadowOpacity: 0.22,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
});
