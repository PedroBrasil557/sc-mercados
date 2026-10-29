/** 08 No mercado: a lista no corredor, com o preço daquela loja e o total do carrinho. Funciona sem sinal. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { Miniatura } from "@/componentes/Miniatura";
import { PainelInferior } from "@/componentes/PainelInferior";
import { PainelPrecoDiferente } from "@/componentes/PainelPrecoDiferente";
import { quantidade, reais, tamanho } from "@/formatar";
import * as armazem from "@/lista/armazem";
import { useComparacao } from "@/lista/comparacao";
import { alternarComprado, type ItemVisivel, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

type Precos = Record<string, number>; // produto -> centavos

export default function NoMercado() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const params = useLocalSearchParams<{ loja?: string }>();
  const { itens, situacao } = useLista();
  const { dados } = useComparacao();
  const lojas = dados?.lojas ?? [];
  const [lojaId, setLojaId] = useState<string | null>(params.loja ?? null);
  const loja = lojas.find((l) => l.loja_id === (lojaId ?? lojas[0]?.loja_id)) ?? null;
  const [precos, setPrecos] = useState<Precos>({});
  const [trocando, setTrocando] = useState(false);
  const [reportando, setReportando] = useState<ItemVisivel | null>(null);

  const produtos = useMemo(() => itens.map((i) => i.produto_id).filter((p): p is string => !!p), [itens]);

  useEffect(() => {
    if (!loja) return;
    const chave = `precos_loja_${loja.loja_id}`;
    let valido = true;
    const guardados = armazem.lerGuardado<Precos>(chave) ?? {};
    api
      .precosNaLoja(loja.loja_id, produtos)
      .then((r) => {
        const novos = Object.fromEntries(Object.entries(r.precos).map(([p, v]) => [p, v.preco_centavos]));
        armazem.guardar(chave, { ...guardados, ...novos });
        if (valido) setPrecos({ ...guardados, ...novos });
      })
      .catch(() => valido && setPrecos(guardados)); // sem sinal no mercado: usa os preços guardados
    return () => {
      valido = false;
    };
  }, [loja, produtos]);

  const ordenados = [...itens].sort((a, b) => Number(a.comprado) - Number(b.comprado));
  const noCarrinho = itens.filter((i) => i.comprado);
  const totalCarrinho = noCarrinho.reduce((s, i) => s + (i.produto_id && precos[i.produto_id] ? precos[i.produto_id]! * i.quantidade : 0), 0);
  const progresso = itens.length ? noCarrinho.length / itens.length : 0;

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela }]}>
      <View style={[estilos.topo, { backgroundColor: cor.fundoProfundo, paddingTop: margem.top + 8 }]}>
        <View style={estilos.barra}>
          <Pressable accessibilityRole="button" accessibilityLabel="Voltar" hitSlop={8} onPress={() => router.back()} style={estilos.voltar}>
            <Icone nome="voltar" cor={cor.textoInverso} />
          </Pressable>
          <Text style={[fonte("tituloSecao"), { color: cor.textoInverso, flex: 1 }]}>No mercado</Text>
          <View style={[estilos.offline, { borderColor: cor.sobreposicaoDivisor }]}>
            <Icone nome="sem-internet" cor={cor.textoInverso} tamanho={16} />
            <Text style={[fonte("legenda"), { color: cor.textoInverso }]}>{situacao.semConexao ? "sem sinal, tudo certo" : "funciona offline"}</Text>
          </View>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Mercado: ${loja?.nome ?? "escolher"}. Toque para trocar`}
          onPress={() => setTrocando(true)}
          style={estilos.loja}
        >
          <Text style={[fonte("rotulo"), { color: cor.textoInverso }]}>{loja?.nome ?? "Escolha o mercado"} · no carrinho</Text>
          <View style={{ transform: [{ rotate: "90deg" }] }}>
            <Icone nome="seta-direita" cor={cor.textoInverso} tamanho={16} />
          </View>
        </Pressable>
        <Text accessibilityLiveRegion="polite" style={[fonte("precoGrande"), { color: cor.textoInverso }]}>
          {reais(totalCarrinho)}
        </Text>
        <View style={[estilos.trilho, { backgroundColor: cor.sobreposicaoDivisor }]}>
          <View style={[estilos.progresso, { width: `${progresso * 100}%`, backgroundColor: cor.marcaEtiqueta }]} />
        </View>
        <Text style={[fonte("corpoMenor"), { color: cor.textoInverso }]}>
          {noCarrinho.length} de {itens.length} itens · faltam {itens.length - noCarrinho.length}
        </Text>
      </View>

      <FlatList
        data={ordenados}
        keyExtractor={(i) => i.id}
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 120 }}
        renderItem={({ item }) => {
          const unitario = item.produto_id ? precos[item.produto_id] : undefined;
          return (
            <View style={[estilos.item, { borderBottomColor: cor.bordaPadrao }]}>
              <Pressable
                accessibilityRole="checkbox"
                accessibilityState={{ checked: item.comprado }}
                accessibilityLabel={`${item.nome}${unitario ? `, ${reais(unitario * item.quantidade)}` : ""}`}
                onPress={() => alternarComprado(item)}
                style={[estilos.linha, item.comprado && { opacity: 0.55 }]}
              >
                <View
                  style={[
                    estilos.caixa,
                    item.comprado ? { backgroundColor: cor.estadoEconomia, borderColor: cor.estadoEconomia } : { borderColor: cor.bordaForte },
                  ]}
                >
                  {item.comprado ? <Icone nome="ok" cor={cor.textoInverso} tamanho={16} /> : null}
                </View>
                <Miniatura categoria={item.categoria} tamanho={tamanho(item.tamanho, item.unidade)} nome={item.nome} />
                <View style={{ flex: 1, gap: 2 }}>
                  <Text numberOfLines={2} style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>
                    {item.nome}
                  </Text>
                  <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.textoSuave }]}>
                    {[`${quantidade(item.quantidade)} un`, item.marca].filter(Boolean).join(" · ")}
                  </Text>
                </View>
                <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal }]}>{unitario ? reais(unitario * item.quantidade) : "—"}</Text>
              </Pressable>
              {!item.comprado && unitario ? (
                <Pressable accessibilityRole="link" onPress={() => setReportando(item)} style={estilos.diferente}>
                  <Icone nome="info" cor={cor.estadoEconomia} tamanho={16} />
                  <Text style={[fonte("legenda"), { color: cor.estadoEconomia }]}>Preço diferente na etiqueta?</Text>
                </Pressable>
              ) : null}
            </View>
          );
        }}
      />

      <View style={[estilos.rodape, { paddingBottom: margem.bottom + 12 }]}>
        <Botao rotulo="Terminei: ler o cupom" tipo="etiqueta" largo aoTocar={() => router.push("/ler-cupom")} />
      </View>

      <PainelInferior visivel={trocando} titulo="Em qual mercado você está?" aoFechar={() => setTrocando(false)}>
        {lojas.map((l) => (
          <Pressable
            key={l.loja_id}
            accessibilityRole="radio"
            accessibilityState={{ checked: l.loja_id === loja?.loja_id }}
            onPress={() => {
              setLojaId(l.loja_id);
              setTrocando(false);
            }}
            style={[estilos.opcao, { borderBottomColor: cor.bordaPadrao }]}
          >
            <Text style={[fonte(l.loja_id === loja?.loja_id ? "corpoForte" : "corpoPadrao"), { color: cor.textoPrincipal, flex: 1 }]}>{l.nome}</Text>
            {l.loja_id === loja?.loja_id ? <Icone nome="ok" cor={cor.estadoEconomia} /> : null}
          </Pressable>
        ))}
      </PainelInferior>

      {reportando && loja && reportando.produto_id ? (
        <PainelPrecoDiferente
          visivel
          aoFechar={() => setReportando(null)}
          produto={{ id: reportando.produto_id, nome: reportando.nome, marca: reportando.marca, categoria: reportando.categoria, tamanho: tamanho(reportando.tamanho, reportando.unidade) }}
          loja={{ id: loja.loja_id, nome: loja.nome, preco_centavos: precos[reportando.produto_id] ?? 0 }}
        />
      ) : null}
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  topo: { paddingHorizontal: 20, paddingBottom: 20, gap: 8, borderBottomLeftRadius: 24, borderBottomRightRadius: 24 },
  barra: { flexDirection: "row", alignItems: "center", gap: 8 },
  voltar: { width: 44, height: 44, alignItems: "center", justifyContent: "center", marginLeft: -10 },
  offline: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderRadius: 16, paddingHorizontal: 10, paddingVertical: 6 },
  loja: { flexDirection: "row", alignItems: "center", gap: 4, minHeight: 32, alignSelf: "flex-start" },
  trilho: { height: 6, borderRadius: 3, overflow: "hidden" },
  progresso: { height: 6, borderRadius: 3 },
  item: { borderBottomWidth: 1, paddingVertical: 10 },
  linha: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56 },
  caixa: { width: 24, height: 24, borderRadius: 6, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  diferente: { flexDirection: "row", alignItems: "center", gap: 6, paddingLeft: 36, minHeight: 36 },
  rodape: { position: "absolute", left: 20, right: 20, bottom: 0 },
  opcao: { flexDirection: "row", alignItems: "center", minHeight: 52, borderBottomWidth: 1 },
});
