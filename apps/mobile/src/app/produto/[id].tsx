/** 06 Detalhe do produto: o preço em cada mercado, de onde veio, e o histórico na loja mais barata. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type DetalheDoProduto, type PrecoNaLoja } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { EtiquetaDePreco } from "@/componentes/EtiquetaDePreco";
import { GraficoDePreco } from "@/componentes/GraficoDePreco";
import { Icone } from "@/componentes/Icone";
import { Miniatura } from "@/componentes/Miniatura";
import { PainelPrecoDiferente } from "@/componentes/PainelPrecoDiferente";
import { SeloDeFonte } from "@/componentes/SeloDeFonte";
import { quantidade, reais, seloDeFonte, tamanho } from "@/formatar";
import { adicionarProduto, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Produto() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { itens } = useLista();
  const [detalhe, setDetalhe] = useState<DetalheDoProduto | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [reportando, setReportando] = useState<PrecoNaLoja | null>(null);

  useEffect(() => {
    let valido = true;
    api
      .produto(id)
      .then((d) => valido && setDetalhe(d))
      .catch(() => valido && setErro("Sem internet: os preços aparecem quando a conexão voltar."));
    return () => {
      valido = false;
    };
  }, [id]);

  const naLista = itens.find((i) => i.produto_id === id && !i.comprado);
  const p = detalhe?.produto;
  const [maisBarato, ...outros] = detalhe?.precos ?? [];

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela }]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 }}>
        <View>
          {p ? (
            <Miniatura porte="G" categoria={p.categoria} marca={p.marca} tamanho={tamanho(p.tamanho, p.unidade)} nome={p.nome} />
          ) : (
            <View style={{ height: 300, backgroundColor: cor.fundoAfundado }} />
          )}
          <View style={[estilos.topo, { top: margem.top + 8 }]}>
            <BotaoRedondo icone="voltar" rotulo="Voltar" aoTocar={() => router.back()} />
            {p ? (
              <BotaoRedondo
                icone="compartilhar"
                rotulo="Compartilhar o preço"
                aoTocar={() =>
                  void Share.share({
                    message: maisBarato
                      ? `${p.nome}: ${reais(maisBarato.preco_centavos)} no ${maisBarato.nome} (SC Mercados)`
                      : `${p.nome} no SC Mercados`,
                  })
                }
              />
            ) : null}
          </View>
          <Pressable accessibilityRole="link" onPress={() => router.push("/dados")} style={estilos.semFoto}>
            <Icone nome="info" cor={cor.textoSuave} tamanho={16} />
            <Text style={[fonte("legenda"), { color: cor.textoSuave, textDecorationLine: "underline" }]}>Por que não tem foto?</Text>
          </Pressable>
        </View>

        <View style={estilos.conteudo}>
          {!detalhe ? (
            <View style={{ gap: 12, paddingTop: 24 }}>
              {erro ? <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>{erro}</Text> : <ActivityIndicator color={cor.estadoEconomia} />}
            </View>
          ) : (
            <>
              <View style={{ gap: 4 }}>
                <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
                  {p?.nome}
                </Text>
                {p?.marca ? <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>{p.marca}</Text> : null}
                {p?.ean ? <SeloDeFonte texto={`EAN ${p.ean.replace(/^0+/, "")}`} /> : null}
              </View>

              {maisBarato ? (
                <View style={[estilos.lojas, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
                  {[maisBarato, ...outros].map((l, i) => {
                    const destaque = i === 0 && outros.length > 0;
                    return (
                      <Pressable
                        key={l.loja_id}
                        accessibilityRole="button"
                        accessibilityLabel={`${l.rede} ${l.bairro ?? ""}: ${reais(l.preco_centavos)}${destaque ? ", mais barato" : ""}`}
                        accessibilityHint="Toque se viu outro preço na prateleira desta loja"
                        onPress={() => setReportando(l)}
                        style={[
                          estilos.loja,
                          destaque && { backgroundColor: cor.estadoEconomiaSuave },
                          i > 0 && { borderTopWidth: 1, borderTopColor: cor.bordaPadrao },
                        ]}
                      >
                        <View style={{ flex: 1, gap: 2 }}>
                          <View style={estilos.nome}>
                            <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{l.rede}</Text>
                            {destaque ? <EtiquetaDePreco /> : null}
                          </View>
                          <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
                            {l.bairro ?? l.nome} · {seloDeFonte(l.fonte, l.observado_em).toLowerCase()}
                            {l.estado === "pode_ter_mudado" ? " · pode ter mudado" : ""}
                          </Text>
                        </View>
                        <View style={{ alignItems: "flex-end" }}>
                          <Text style={[fonte("precoMedio"), { color: destaque ? cor.estadoEconomia : cor.textoPrincipal }]}>{reais(l.preco_centavos)}</Text>
                          {l.preco_de_centavos && l.preco_de_centavos > l.preco_centavos ? (
                            <Text style={[fonte("legenda"), { color: cor.textoSuave, textDecorationLine: "line-through" }]}>
                              antes {reais(l.preco_de_centavos)}
                            </Text>
                          ) : null}
                        </View>
                      </Pressable>
                    );
                  })}
                </View>
              ) : (
                <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>Ainda não temos o preço deste produto nas lojas perto de você.</Text>
              )}

              {maisBarato && detalhe.historico.length ? (
                <View style={[estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
                  <View style={estilos.nome}>
                    <Icone nome="historico" cor={cor.textoPrincipal} />
                    <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal, flex: 1 }]}>Preço no {maisBarato.rede}, últimos 30 dias</Text>
                  </View>
                  <GraficoDePreco pontos={detalhe.historico} />
                </View>
              ) : null}

              {maisBarato ? (
                <Pressable
                  accessibilityRole="link"
                  onPress={() => setReportando(maisBarato)}
                  style={estilos.link}
                >
                  <Icone nome="info" cor={cor.estadoEconomia} tamanho={16} />
                  <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>Viu outro preço na prateleira?</Text>
                </Pressable>
              ) : null}
            </>
          )}
        </View>
      </ScrollView>

      {p ? (
        <PainelPrecoDiferente
          visivel={!!reportando}
          aoFechar={() => setReportando(null)}
          produto={{ id: p.id, nome: p.nome, marca: p.marca, categoria: p.categoria, tamanho: tamanho(p.tamanho, p.unidade) }}
          loja={reportando ? { id: reportando.loja_id, nome: reportando.nome, preco_centavos: reportando.preco_centavos } : null}
        />
      ) : null}
      {p ? (
        <View style={[estilos.rodape, { paddingBottom: margem.bottom + 12 }]}>
          <Botao
            largo
            rotulo={naLista ? `Na sua lista · ${quantidade(naLista.quantidade)} ${naLista.quantidade === 1 ? "unidade" : "unidades"} · somar 1` : "Pôr na lista"}
            aoTocar={() => adicionarProduto(p)}
          />
        </View>
      ) : null}
    </View>
  );
}

function BotaoRedondo({ icone, rotulo, aoTocar }: { icone: "voltar" | "compartilhar"; rotulo: string; aoTocar: () => void }) {
  const { cor } = useTema();
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={rotulo} onPress={aoTocar} style={[estilos.redondo, { backgroundColor: cor.fundoSuperficie }]}>
      <Icone nome={icone} cor={cor.textoPrincipal} tamanho={20} />
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  topo: { position: "absolute", left: 16, right: 16, flexDirection: "row", justifyContent: "space-between" },
  redondo: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center" },
  semFoto: { position: "absolute", bottom: 12, alignSelf: "center", flexDirection: "row", alignItems: "center", gap: 6, minHeight: 44 },
  conteudo: { paddingHorizontal: 20, paddingTop: 20, gap: 16 },
  lojas: { borderRadius: 20, borderWidth: 1, overflow: "hidden" },
  loja: { flexDirection: "row", alignItems: "center", gap: 12, padding: 16 },
  nome: { flexDirection: "row", alignItems: "center", gap: 8 },
  cartao: { borderRadius: 20, borderWidth: 1, padding: 16, gap: 12 },
  link: { flexDirection: "row", alignItems: "center", gap: 6, minHeight: 44 },
  rodape: { position: "absolute", left: 20, right: 20, bottom: 0 },
});
