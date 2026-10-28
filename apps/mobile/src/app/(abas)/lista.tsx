/**
 * Lista da casa: versão PROVISÓRIA e funcional, para testar a sincronia no celular.
 * O desenho final (Figma, telas 03 e seguintes) entra depois do teste com as famílias.
 */
import { useEffect, useState } from "react";
import { Alert, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { Produto } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Campo } from "@/componentes/Campo";
import {
  adicionarProduto,
  alternarComprado,
  buscarProdutos,
  comecarCasa,
  entrarComConvite,
  type ItemVisivel,
  remover,
  type Situacao,
  somar,
  tirar,
  useLista,
} from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Lista() {
  const { sessao, itens, situacao } = useLista();
  const { cor, medida } = useTema();
  const margem = useSafeAreaInsets();
  const [busca, setBusca] = useState("");

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + medida.espaco4 }]}>
      {!sessao ? (
        <Entrada />
      ) : (
        <>
          <View style={{ paddingHorizontal: medida.espaco5, gap: medida.espaco3 }}>
            <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
              Lista da casa
            </Text>
            <SituacaoDaSincronia situacao={situacao} />
            <Campo rotulo="Buscar produto para pôr na lista" placeholder="O que está faltando em casa?" value={busca} onChangeText={setBusca} />
          </View>
          {busca.trim() ? (
            <ResultadosDaBusca busca={busca} aoEscolher={() => setBusca("")} />
          ) : (
            <FlatList
              data={itens}
              keyExtractor={(i) => i.id}
              contentContainerStyle={{ padding: medida.espaco5, gap: medida.espaco2 }}
              renderItem={({ item }) => <LinhaDoItem item={item} />}
              ListEmptyComponent={
                <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>Lista vazia. Busque um produto acima para começar.</Text>
              }
            />
          )}
        </>
      )}
    </View>
  );
}

function Entrada() {
  const { cor, medida } = useTema();
  const [apelido, setApelido] = useState("");
  const [codigo, setCodigo] = useState("");
  const [ocupado, setOcupado] = useState<"nova" | "convite" | null>(null);

  async function tentar(tipo: "nova" | "convite") {
    if (!apelido.trim()) return Alert.alert("Como você quer ser chamado?", "Escreva um apelido para a família saber quem mexeu na lista.");
    setOcupado(tipo);
    try {
      if (tipo === "nova") await comecarCasa(apelido);
      else await entrarComConvite(codigo, apelido);
    } catch (e) {
      Alert.alert("Não deu certo", e instanceof Error ? e.message : "Tente de novo em instantes.");
    } finally {
      setOcupado(null);
    }
  }

  return (
    <View style={{ paddingHorizontal: medida.espaco5, gap: medida.espaco4 }}>
      <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
        Lista da casa
      </Text>
      <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
        Uma lista só para a família toda, que funciona mesmo sem internet.
      </Text>
      <Campo rotulo="Seu apelido" placeholder="Como você quer ser chamado?" value={apelido} onChangeText={setApelido} maxLength={40} />
      <Botao rotulo="Começar a lista da minha casa" aoTocar={() => void tentar("nova")} ocupado={ocupado === "nova"} />
      <Text style={[fonte("rotulo"), { color: cor.textoSuave, marginTop: medida.espaco4 }]}>Já tem uma casa no SC Mercados?</Text>
      <Campo
        rotulo="Código de convite"
        placeholder="Código de 8 letras"
        value={codigo}
        onChangeText={setCodigo}
        autoCapitalize="characters"
        autoCorrect={false}
        maxLength={10}
      />
      <Botao rotulo="Entrar na casa" tipo="secundario" aoTocar={() => void tentar("convite")} ocupado={ocupado === "convite"} />
    </View>
  );
}

function SituacaoDaSincronia({ situacao }: { situacao: Situacao }) {
  const { cor } = useTema();
  const [ponto, texto] = situacao.erro
    ? [cor.estadoAlerta, `Problema ao sincronizar: ${situacao.erro}`]
    : situacao.semConexao
      ? [cor.bordaForte, `Sem conexão. ${situacao.pendentes ? `${situacao.pendentes} mudança(s) guardada(s) no celular.` : "A lista continua funcionando."}`]
      : situacao.pendentes
        ? [cor.marcaEtiqueta, `${situacao.pendentes} mudança(s) aguardando envio…`]
        : [cor.estadoEconomia, situacao.ultimaSincronia ? "Tudo sincronizado com a casa" : "Sincronizando…"];
  return (
    <View accessibilityRole="summary" accessibilityLiveRegion="polite" style={estilos.situacao}>
      <View style={[estilos.ponto, { backgroundColor: ponto }]} />
      <Text style={[fonte("legenda"), { color: cor.textoSuave, flex: 1 }]}>{texto}</Text>
    </View>
  );
}

function LinhaDoItem({ item }: { item: ItemVisivel }) {
  const { cor, medida } = useTema();
  const quantidade = Number.isInteger(item.quantidade) ? String(item.quantidade) : item.quantidade.toLocaleString("pt-BR");
  return (
    <View style={[estilos.item, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderRadius: medida.raioMedio }]}>
      <Pressable
        style={estilos.itemTexto}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: item.comprado }}
        accessibilityLabel={`${item.nome}, ${quantidade}`}
        accessibilityHint="Toque para marcar como comprado. Toque e segure para tirar da lista."
        onPress={() => alternarComprado(item)}
        onLongPress={() =>
          Alert.alert("Tirar da lista?", item.nome, [
            { text: "Cancelar", style: "cancel" },
            { text: "Tirar", style: "destructive", onPress: () => remover(item.id) },
          ])
        }
      >
        <Text
          numberOfLines={2}
          style={[fonte("corpoForte"), { color: item.comprado ? cor.textoSuave : cor.textoPrincipal }, item.comprado && estilos.riscado]}
        >
          {item.nome}
        </Text>
        <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
          {[item.marca, item.adicionado_por && `por ${item.adicionado_por}`].filter(Boolean).join(" · ")}
        </Text>
        {item.aviso ? <Text style={[fonte("legenda"), { color: cor.estadoAlerta }]}>{item.aviso}</Text> : null}
      </Pressable>
      <View style={estilos.quantidade}>
        <BotaoRedondo rotulo={`Tirar um de ${item.nome}`} simbolo="−" aoTocar={() => tirar(item.id)} />
        <Text style={[fonte("numeroQuantidade"), estilos.numero, { color: cor.textoPrincipal }]}>{quantidade}</Text>
        <BotaoRedondo rotulo={`Somar um de ${item.nome}`} simbolo="+" aoTocar={() => somar(item.id)} />
      </View>
    </View>
  );
}

function BotaoRedondo({ rotulo, simbolo, aoTocar }: { rotulo: string; simbolo: string; aoTocar: () => void }) {
  const { cor } = useTema();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      onPress={aoTocar}
      hitSlop={6}
      style={({ pressed }) => [estilos.redondo, { borderColor: cor.bordaForte }, pressed && { backgroundColor: cor.fundoAfundado }]}
    >
      <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{simbolo}</Text>
    </Pressable>
  );
}

function ResultadosDaBusca({ busca, aoEscolher }: { busca: string; aoEscolher: () => void }) {
  const { cor, medida } = useTema();
  const [resultado, setResultado] = useState<{ produtos: Produto[]; semConexao: boolean } | null>(null);

  useEffect(() => {
    let valido = true;
    const espera = setTimeout(() => {
      void buscarProdutos(busca).then((r) => valido && setResultado(r));
    }, 250);
    return () => {
      valido = false;
      clearTimeout(espera);
    };
  }, [busca]);

  if (!resultado) return <Text style={[fonte("legenda"), { color: cor.textoSuave, padding: medida.espaco5 }]}>Buscando…</Text>;
  return (
    <FlatList
      data={resultado.produtos}
      keyExtractor={(p) => p.id}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ padding: medida.espaco5, gap: medida.espaco2 }}
      ListHeaderComponent={
        resultado.semConexao ? (
          <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Sem conexão: buscando no catálogo guardado no celular.</Text>
        ) : undefined
      }
      ListEmptyComponent={<Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>Nada encontrado para “{busca}”.</Text>}
      renderItem={({ item }) => (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Pôr ${item.nome} na lista`}
          onPress={() => {
            adicionarProduto(item);
            aoEscolher();
          }}
          style={({ pressed }) => [
            estilos.resultado,
            { backgroundColor: pressed ? cor.fundoAfundado : cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderRadius: medida.raioMedio },
          ]}
        >
          <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{item.nome}</Text>
          {item.marca ? <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{item.marca}</Text> : null}
        </Pressable>
      )}
    />
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1, gap: 8 },
  situacao: { flexDirection: "row", alignItems: "center", gap: 8 },
  ponto: { width: 8, height: 8, borderRadius: 4 },
  item: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderWidth: StyleSheet.hairlineWidth },
  itemTexto: { flex: 1, minHeight: 44, justifyContent: "center", gap: 2 },
  riscado: { textDecorationLine: "line-through" },
  quantidade: { flexDirection: "row", alignItems: "center", gap: 6 },
  numero: { minWidth: 28, textAlign: "center" },
  redondo: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  resultado: { padding: 14, borderWidth: StyleSheet.hairlineWidth, gap: 2 },
});
