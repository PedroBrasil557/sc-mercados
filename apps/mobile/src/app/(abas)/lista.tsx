/** R5 Lista da casa (e 16 Lista vazia): agrupada por corredor, com o preço de cada item no seu mercado e o total.
 * "Qualquer marca" mostra a marca mais barata de hoje; item que o seu mercado não vende avisa. */
import { router } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, SectionList, Share, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Inicio } from "@/api/cliente";
import { AvisoComDesfazer } from "@/componentes/AvisoComDesfazer";
import { Botao } from "@/componentes/Botao";
import { Chip } from "@/componentes/Chip";
import { Icone } from "@/componentes/Icone";
import { ItemDaLista } from "@/componentes/ItemDaLista";
import { PainelRecuperacao } from "@/componentes/PainelRecuperacao";
import { SeletorDeMercado } from "@/componentes/SeletorDeMercado";
import { haQuanto, quantidade, reais } from "@/formatar";
import * as armazem from "@/lista/armazem";
import { useComparacao } from "@/lista/comparacao";
import { useGuardado } from "@/lista/guardado";
import { useMercados } from "@/lista/mercado";
import { type ItemVisivel, remover, restaurar, somar, tirar, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

// Sugestões da lista vazia: cada uma abre a busca já preenchida.
const COMECE_POR = ["Leite", "Arroz", "Café", "Feijão", "Açúcar", "Óleo"];
// Ordem dos corredores num mercado comum: da entrada (hortifrúti, padaria) ao fundo (limpeza, higiene).
const CORREDORES: Record<string, string> = {
  hortifruti: "Hortifrúti",
  padaria: "Padaria",
  mercearia: "Mercearia",
  graos: "Grãos e massas",
  cafe: "Café e chás",
  doces: "Doces e biscoitos",
  laticinios: "Laticínios",
  bebidas: "Bebidas",
  limpeza: "Limpeza",
  higiene: "Higiene",
};
const ORDEM = Object.keys(CORREDORES);

/** Preço de cada produto no seu mercado (inclui a marca escolhida para os itens "qualquer marca"). */
function usePrecosNoSeuMercado(ids: string[], lojaId: string | null) {
  const [precos, setPrecos] = useState<Record<string, number> | null>(null);
  const chave = `${lojaId}|${ids.join(",")}`;
  useEffect(() => {
    if (!lojaId || !ids.length) return;
    let valido = true;
    const espera = setTimeout(() => {
      api
        .precosNaLoja(lojaId, ids)
        .then((r) => valido && setPrecos(Object.fromEntries(Object.entries(r.precos).map(([k, v]) => [k, v.preco_centavos]))))
        .catch(() => undefined);
    }, 400);
    return () => {
      valido = false;
      clearTimeout(espera);
    };
    // a chave resume ids e loja
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);
  return precos;
}

export default function Lista() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao, itens, situacao } = useLista();
  const { dados } = useComparacao();
  const mercados = useMercados();
  const inicio = useGuardado<Inicio>("inicio", api.inicio);
  const [removido, setRemovido] = useState<ItemVisivel | null>(null);
  const sumirAviso = useCallback(() => setRemovido(null), []);
  // R16: com 10 itens a lista já vale a pena guardar; o convite aparece uma vez só.
  const [recuperacaoDispensada, setRecuperacaoDispensada] = useState(() => armazem.lerGuardado<boolean>("recuperacao_oferecida") ?? false);
  const oferecerRecuperacao = itens.length >= 10 && !recuperacaoDispensada;
  const dispensarRecuperacao = () => {
    armazem.guardar("recuperacao_oferecida", true);
    setRecuperacaoDispensada(true);
  };

  const seu = mercados?.seu_mercado ?? null;
  const lojaDoSeu = dados?.lojas.find((l) => l.loja_id === seu?.loja_id);
  const escolhas = useMemo(() => new Map((lojaDoSeu?.escolhas ?? []).map((e) => [e.item, e])), [lojaDoSeu]);
  const aComprar = itens.filter((i) => !i.comprado);
  const ids = useMemo(
    () => [...new Set(aComprar.filter((i) => i.produto_id).map((i) => escolhas.get(i.produto_id!)?.produto_id ?? i.produto_id!))].sort(),
    [aComprar, escolhas],
  );
  const precos = usePrecosNoSeuMercado(ids, seu?.loja_id ?? null);
  const precoDe = (i: ItemVisivel) => {
    if (!i.produto_id || !precos) return undefined;
    const escolha = i.qualquer_marca ? escolhas.get(i.produto_id) : undefined;
    const valor = precos[escolha?.produto_id ?? i.produto_id];
    return valor ? { unitario: valor, marcaDeHoje: escolha?.marca } : null;
  };

  const secoes = useMemo(() => {
    const grupos = new Map<string, ItemVisivel[]>();
    for (const i of aComprar) {
      const c = i.categoria && CORREDORES[i.categoria] ? i.categoria : "mercearia";
      grupos.set(c, [...(grupos.get(c) ?? []), i]);
    }
    const comprados = itens.filter((i) => i.comprado);
    const s = ORDEM.filter((c) => grupos.has(c)).map((c) => ({ chave: c, titulo: CORREDORES[c]!, data: grupos.get(c)! }));
    if (comprados.length) s.push({ chave: "comprados", titulo: "Já no carrinho", data: comprados });
    return s;
  }, [aComprar, itens]);

  const totalAqui = precos ? aComprar.reduce((soma, i) => soma + (precoDe(i)?.unitario ?? 0) * i.quantidade, 0) : null;
  const comPreco = precos ? aComprar.filter((i) => precoDe(i)).length : 0;
  const recomendada = dados?.lojas[0];
  const buscar = (termo = "") => router.push({ pathname: "/adicionar", params: termo ? { busca: termo } : {} });
  const pessoas = sessao ? Object.values(sessao.nomes).map((n) => (n === sessao.apelido ? "você" : n)) : [];
  const subtitulo = itens.length ? `${itens.length} ${itens.length === 1 ? "item" : "itens"} · ${juntar(pessoas)}` : "Nenhum item ainda";
  const atividade = inicio.dados?.atividade[0];

  async function compartilhar() {
    const linhas = aComprar.map((i) => `• ${i.nome_curto ?? i.nome}${i.qualquer_marca ? " (qualquer marca)" : ""}${i.quantidade !== 1 ? ` (${quantidade(i.quantidade)})` : ""}`);
    await Share.share({ message: `Lista da casa no SC Mercados:\n${linhas.join("\n")}` });
  }

  const cabecalho = (
    <View style={{ gap: 12, paddingBottom: 8 }}>
      {atividade ? (
        <View style={[estilos.atividade, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
          <View style={[estilos.avatar, { backgroundColor: cor.marcaEtiqueta }]}>
            <Text style={[fonte("corpoForte"), { color: cor.marcaSobreEtiqueta }]}>{(atividade.quem ?? "?").charAt(0).toUpperCase()}</Text>
          </View>
          <Text style={[fonte("corpoMenor"), { color: cor.textoPrincipal, flex: 1 }]}>
            {atividade.quem ?? "Alguém"} {atividade.tipo === "marcar" ? "comprou" : atividade.tipo === "remover" ? "tirou" : "pôs"} {atividade.item} {haQuanto(atividade.quando)}
          </Text>
        </View>
      ) : null}
      <SeletorDeMercado />
      {aComprar.length && totalAqui !== null ? (
        <Pressable
          accessibilityRole="button"
          onPress={() => router.navigate("/comparar")}
          style={[estilos.total, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}
        >
          <View style={estilos.linhaTotal}>
            <Text style={[fonte("precoGrande"), { color: cor.textoPrincipal }]}>{reais(totalAqui)}</Text>
            {recomendada?.loja_id === seu?.loja_id ? (
              <View style={[estilos.etiqueta, { backgroundColor: cor.marcaEtiqueta }]}>
                <Text style={[fonte("rotulo"), { color: cor.marcaSobreEtiqueta }]}>MELHOR PARA VOCÊ</Text>
              </View>
            ) : null}
          </View>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
            {comPreco} de {aComprar.length} itens com preço no {seu?.nome}
          </Text>
          {recomendada && recomendada.loja_id !== seu?.loja_id ? (
            <Text style={[fonte("corpoForte"), { color: cor.estadoEconomia }]}>Hoje sai melhor no {recomendada.nome}: ver por quê ›</Text>
          ) : comPreco < aComprar.length ? (
            <Text style={[fonte("corpoForte"), { color: cor.estadoEconomia }]}>
              {aComprar.length - comPreco} {aComprar.length - comPreco === 1 ? "item não tem" : "itens não têm"} aqui: ver na comparação ›
            </Text>
          ) : null}
        </Pressable>
      ) : null}
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
  );

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

      {itens.length ? (
        <SectionList
          sections={secoes}
          keyExtractor={(i) => i.id}
          stickySectionHeadersEnabled={false}
          contentContainerStyle={[estilos.margens, { paddingBottom: 120 }]}
          ListHeaderComponent={cabecalho}
          renderSectionHeader={({ section }) => {
            const soma = precos ? section.data.reduce((s, i) => s + (i.comprado ? 0 : (precoDe(i)?.unitario ?? 0) * i.quantidade), 0) : 0;
            return (
              <View style={estilos.secao}>
                <Text style={[fonte("rotulo"), { color: cor.textoSuave, flex: 1 }]}>
                  {section.titulo} · {section.data.length} {section.data.length === 1 ? "item" : "itens"}
                </Text>
                {soma ? <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>{reais(soma)}</Text> : null}
              </View>
            );
          }}
          renderItem={({ item }) => {
            const preco = item.comprado ? undefined : precoDe(item);
            return (
              <ItemDaLista
                item={item}
                meuNome={sessao?.apelido ?? ""}
                preco={preco}
                semPrecoAqui={preco === null}
                aoSomar={() => somar(item.id)}
                aoTirar={() => {
                  if (item.quantidade <= 1) setRemovido(item);
                  tirar(item.id);
                }}
                aoTocar={() => item.produto_id && router.push({ pathname: "/produto/[id]", params: { id: item.produto_id } })}
                aoSegurar={() => {
                  setRemovido(item);
                  remover(item.id);
                }}
              />
            );
          }}
        />
      ) : (
        <View style={[estilos.margens, estilos.vazio]}>
          <View style={[estilos.ilustracao, { backgroundColor: cor.estadoEconomiaSuave }]}>
            <Icone nome="lista" cor={cor.estadoEconomia} tamanho={40} />
          </View>
          <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal, textAlign: "center" }]}>O que está faltando em casa?</Text>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>
            Anote aqui. O app mostra na hora quanto a lista custa no seu mercado e se vale ir em outro.
          </Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, alignSelf: "flex-start", marginTop: 16 }]}>Comece por estes</Text>
          <View style={estilos.chips}>
            {COMECE_POR.map((s) => (
              <Chip key={s} texto={`+ ${s}`} aoTocar={() => buscar(s)} />
            ))}
          </View>
        </View>
      )}

      <PainelRecuperacao visivel={oferecerRecuperacao} aoFechar={dispensarRecuperacao} />
      <View style={[estilos.rodape, { paddingBottom: 12 }]} pointerEvents="box-none">
        {removido ? (
          <AvisoComDesfazer
            texto={`${removido.nome_curto ?? removido.nome} saiu da lista`}
            aoSumir={sumirAviso}
            aoDesfazer={() => {
              restaurar(removido.id, removido.quantidade);
              setRemovido(null);
            }}
          />
        ) : seu && aComprar.length && totalAqui ? (
          <View style={[estilos.resumo, { backgroundColor: cor.fundoProfundo }]}>
            <View style={{ flex: 1 }}>
              <Text numberOfLines={1} style={[fonte("precoMedio"), { color: cor.textoInverso }]}>
                {reais(totalAqui)}
              </Text>
              <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.textoInverso }]}>
                no {seu.nome}
              </Text>
            </View>
            <Botao rotulo="No mercado" tipo="etiqueta" aoTocar={() => router.push({ pathname: "/no-mercado", params: { loja: seu.loja_id } })} />
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
  atividade: { flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: 14, borderWidth: 1 },
  avatar: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  total: { padding: 16, borderRadius: 20, borderWidth: 1, gap: 6 },
  linhaTotal: { flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" },
  etiqueta: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  busca: { height: 54, borderRadius: 27, borderWidth: 1.5, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16 },
  situacao: { flexDirection: "row", alignItems: "center", gap: 6 },
  secao: { flexDirection: "row", alignItems: "center", gap: 8, paddingTop: 16, paddingBottom: 4 },
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
