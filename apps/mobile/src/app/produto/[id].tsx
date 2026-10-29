/** R6 Produto: o preço no seu mercado primeiro, se vale ir em outro (com a viagem), uma linha por rede,
 * as marcas equivalentes mais baratas no seu mercado e o histórico. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type DetalheDoProduto, type PrecoNaLoja } from "@/api/cliente";
import { MarcaDaRede } from "@/componentes/MarcaDaRede";
import { Botao } from "@/componentes/Botao";
import { EtiquetaDePreco } from "@/componentes/EtiquetaDePreco";
import { GraficoDePreco } from "@/componentes/GraficoDePreco";
import { Icone } from "@/componentes/Icone";
import { Miniatura } from "@/componentes/Miniatura";
import { PainelPrecoDiferente } from "@/componentes/PainelPrecoDiferente";
import { SeloDeFonte } from "@/componentes/SeloDeFonte";
import { confirmar } from "@/componentes/Confirmacao";
import { km, marca, quantidade, reais, seloDeFonte, tamanho } from "@/formatar";
import { custoKm } from "@/lista/comparacao";
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
      .produto(id, custoKm())
      .then((d) => valido && setDetalhe(d))
      .catch(() => valido && setErro("Sem internet: os preços aparecem quando a conexão voltar."));
    return () => {
      valido = false;
    };
  }, [id]);

  const naLista = itens.find((i) => i.produto_id === id && !i.comprado && !i.qualquer_marca);
  const p = detalhe?.produto;
  const [maisBarato] = detalhe?.precos ?? [];
  const seu = detalhe?.seu_mercado ?? null;
  const linhaDoSeu = detalhe?.por_rede?.find((l) => seu && l.loja_id === seu.loja_id);
  const outrasRedes = (detalhe?.por_rede ?? []).filter((l) => !seu || l.loja_id !== seu.loja_id);
  const menorPreco = Math.min(...outrasRedes.map((l) => l.preco_centavos ?? Infinity));
  const pôr = (qualquerMarca: boolean) => {
    if (!p) return;
    adicionarProduto(p, { qualquerMarca });
    confirmar(`Na lista: ${p.nome_curto ?? p.nome}${qualquerMarca ? " (qualquer marca)" : ""}`);
  };

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
                  {p?.nome_curto ?? p?.nome}
                </Text>
                <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
                  {[marca(p?.marca), tamanho(p?.tamanho ?? null, p?.unidade ?? null)].filter(Boolean).join(" · ")}
                </Text>
                {p?.ean ? <SeloDeFonte texto={`EAN ${p.ean.replace(/^0+/, "")}`} /> : null}
              </View>

              {seu ? (
                <View style={[estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.estadoEconomia, borderWidth: 1.5 }]}>
                  <Text style={[fonte("rotulo"), { color: cor.estadoEconomia }]}>NO SEU MERCADO</Text>
                  {seu.preco_centavos ? (
                    <>
                      <View style={estilos.nome}>
                        <View style={{ flex: 1, gap: 2 }}>
                          <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{seu.nome}</Text>
                          <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
                            {km(seu.distancia_km)}
                            {(linhaDoSeu?.lojas_mesmo_preco ?? 0) > 1 ? ` · mesmo preço nas ${linhaDoSeu?.lojas_mesmo_preco} lojas ${seu.rede}` : ""}
                          </Text>
                        </View>
                        <View style={{ alignItems: "flex-end" }}>
                          <Text style={[fonte("precoGrande"), { color: cor.textoPrincipal }]}>{reais(seu.preco_centavos)}</Text>
                          {seu.preco_por_unidade ? <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{seu.preco_por_unidade}</Text> : null}
                        </View>
                      </View>
                      {seu.observado_em ? <SeloDeFonte texto={seloDeFonte(seu.fonte ?? "site", seu.observado_em)} /> : null}
                    </>
                  ) : (
                    <Text style={[fonte("corpoPadrao"), { color: cor.textoPrincipal }]}>
                      O {seu.nome} não vende este produto.{detalhe.equivalentes?.length ? " Veja abaixo os do mesmo tipo que ele vende." : ""}
                    </Text>
                  )}
                </View>
              ) : null}

              {detalhe.veredito ? (
                <View style={[estilos.veredito, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
                  <View style={[estilos.iconeRedondo, { backgroundColor: cor.estadoEconomiaSuave }]}>
                    <Icone nome="rota" cor={cor.estadoEconomia} tamanho={20} />
                  </View>
                  <View style={{ flex: 1, gap: 4 }}>
                    <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>Vale ir em outro mercado?</Text>
                    <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
                      No {detalhe.veredito.rede} sai {reais(detalhe.veredito.economia_centavos)} mais barato
                      {detalhe.veredito.viagem_centavos
                        ? `, mas a ida e volta a mais (${km(detalhe.veredito.km_ida_e_volta)}) custa cerca de ${reais(detalhe.veredito.viagem_centavos)}`
                        : ""}
                      .{" "}
                      {detalhe.veredito.compensa ? "Compensa ir até lá." : "Só por este item, não compensa; vale se você já for passar lá."}
                    </Text>
                  </View>
                </View>
              ) : null}

              {outrasRedes.length ? (
                <>
                  <Text accessibilityRole="header" style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>
                    {seu ? "Nos outros mercados" : "Nos mercados perto de você"}
                  </Text>
                  <View style={[estilos.lojas, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
                    {outrasRedes.map((l, i) => {
                      const barato = l.preco_centavos !== null && l.preco_centavos === menorPreco;
                      const preco = detalhe.precos.find((x) => x.loja_id === l.loja_id);
                      return (
                        <Pressable
                          key={l.loja_id}
                          accessibilityRole="button"
                          accessibilityLabel={`${l.rede} ${l.bairro ?? ""}: ${l.preco_centavos ? reais(l.preco_centavos) : (l.motivo ?? "sem preço")}`}
                          accessibilityHint={preco ? "Toque se viu outro preço na prateleira desta loja" : undefined}
                          disabled={!preco}
                          onPress={() => preco && setReportando(preco)}
                          style={[estilos.loja, i > 0 && { borderTopWidth: 1, borderTopColor: cor.bordaPadrao }]}
                        >
                          <MarcaDaRede rede={l.rede} tamanho={32} />
                          <View style={{ flex: 1, gap: 2 }}>
                            <View style={estilos.nome}>
                              <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{l.rede}</Text>
                              {barato && outrasRedes.length > 1 ? <EtiquetaDePreco /> : null}
                            </View>
                            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
                              {l.bairro ?? l.nome} · {km(l.distancia_km)}
                              {l.motivo ? ` · ${l.motivo}` : ""}
                              {(l.lojas_mesmo_preco ?? 0) > 1 ? ` · mesmo preço em ${l.lojas_mesmo_preco} lojas` : ""}
                            </Text>
                          </View>
                          <Text style={[fonte("precoMedio"), { color: l.preco_centavos ? cor.textoPrincipal : cor.textoSuave }]}>
                            {l.preco_centavos ? reais(l.preco_centavos) : "—"}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </>
              ) : !seu?.preco_centavos ? (
                <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>Ainda não temos o preço deste produto nas lojas perto de você.</Text>
              ) : null}

              {detalhe.equivalentes?.length ? (
                <>
                  <Text accessibilityRole="header" style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>
                    Mais barato no seu mercado
                  </Text>
                  <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, marginTop: -8 }]}>
                    Mesmo tipo e tamanho, outra marca. Ou ponha “qualquer marca” na lista.
                  </Text>
                  <View>
                    {detalhe.equivalentes.map((e) => (
                      <Pressable
                        key={e.produto_id}
                        accessibilityRole="button"
                        onPress={() => router.push({ pathname: "/produto/[id]", params: { id: e.produto_id } })}
                        style={[estilos.equivalente, { borderBottomColor: cor.bordaPadrao }]}
                      >
                        <Miniatura categoria={p?.categoria ?? null} tamanho={tamanho(e.tamanho, e.unidade)} nome={e.nome_curto} />
                        <View style={{ flex: 1, gap: 2 }}>
                          <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{e.nome_curto}</Text>
                          <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{[e.marca, tamanho(e.tamanho, e.unidade)].filter(Boolean).join(" · ")}</Text>
                          {e.economia_centavos ? (
                            <Text style={[fonte("legenda"), { color: cor.estadoEconomia }]}>{reais(e.economia_centavos)} a menos</Text>
                          ) : null}
                        </View>
                        <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal }]}>{reais(e.preco_centavos)}</Text>
                      </Pressable>
                    ))}
                  </View>
                </>
              ) : null}

              {detalhe.historico.length ? (
                <View style={[estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
                  <View style={estilos.nome}>
                    <Icone nome="historico" cor={cor.textoPrincipal} />
                    <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal, flex: 1 }]}>
                      Preço no {seu?.preco_centavos ? seu.rede : maisBarato?.rede}, últimos 30 dias
                    </Text>
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
          {naLista ? (
            <Botao largo rotulo={`Na sua lista · ${quantidade(naLista.quantidade)} · somar 1`} aoTocar={() => pôr(false)} />
          ) : (
            <View style={estilos.botoes}>
              {detalhe?.grupo ? (
                <View style={{ flex: 1 }}>
                  <Botao largo tipo="contorno" rotulo="Qualquer marca" aoTocar={() => pôr(true)} />
                </View>
              ) : null}
              <View style={{ flex: 1 }}>
                <Botao largo rotulo={detalhe?.grupo ? "Pôr esta marca" : "Pôr na lista"} aoTocar={() => pôr(false)} />
              </View>
            </View>
          )}
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
  botoes: { flexDirection: "row", gap: 12 },
  veredito: { flexDirection: "row", gap: 12, padding: 16, borderRadius: 20, borderWidth: 1 },
  iconeRedondo: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  equivalente: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, borderBottomWidth: 1 },
});
