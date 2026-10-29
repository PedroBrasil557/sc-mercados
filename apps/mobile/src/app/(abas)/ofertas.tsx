/** R8 Ofertas reais (R9): só entra quando o preço caiu de verdade. Do seu mercado para o mais longe, com filtro
 * de onde (perto, seu mercado, da sua lista) e de categoria; "+" põe na lista sem abrir o produto. */
import { router } from "expo-router";
import { useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Mercado, type Oferta } from "@/api/cliente";
import { MarcaDaRede } from "@/componentes/MarcaDaRede";
import { ChaveDoAviso, ExplicacaoDosAvisos, useAvisoDeQuinta } from "@/componentes/AvisoDeQuinta";
import { CartaoDeOferta } from "@/componentes/CartaoDeOferta";
import { Chip } from "@/componentes/Chip";
import { confirmar } from "@/componentes/Confirmacao";
import { Icone } from "@/componentes/Icone";
import { km } from "@/formatar";
import { useGuardado } from "@/lista/guardado";
import { adicionarProduto, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

const PERTO_KM = 5;
const CATEGORIAS: Record<string, string> = {
  mercearia: "Mercearia",
  graos: "Grãos",
  laticinios: "Laticínios",
  bebidas: "Bebidas",
  cafe: "Café",
  doces: "Doces",
  limpeza: "Limpeza",
  higiene: "Higiene",
  padaria: "Padaria",
  hortifruti: "Hortifrúti",
};
type Onde = "perto" | "seu" | "lista" | "todas";

export default function Ofertas() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { itens } = useLista();
  const aviso = useAvisoDeQuinta();
  const r = useGuardado<{ ofertas: Oferta[]; seu_mercado: Mercado | null }>("ofertas", api.ofertas);
  const [onde, setOnde] = useState<Onde>("perto");
  const [categoria, setCategoria] = useState<string | null>(null);

  const todas = useMemo(() => r.dados?.ofertas ?? [], [r.dados]);
  const daLista = useMemo(() => new Set(itens.filter((i) => !i.comprado).map((i) => i.produto_id)), [itens]);
  const minhas = todas.filter((o) => daLista.has(o.produto.id)).length;
  const filtradas = todas.filter(
    (o) =>
      (onde === "todas" || (onde === "perto" && (o.seu_mercado || o.distancia_km <= PERTO_KM)) || (onde === "seu" && o.seu_mercado) || (onde === "lista" && daLista.has(o.produto.id))) &&
      (!categoria || o.produto.categoria === categoria),
  );
  const categorias = [...new Set(todas.map((o) => o.produto.categoria))].filter((c) => CATEGORIAS[c]);
  // Uma seção por loja: o seu mercado primeiro, depois do mais perto para o mais longe.
  const lojas = useMemo(() => {
    const m = new Map<string, Oferta[]>();
    for (const o of filtradas) m.set(o.loja_id, [...(m.get(o.loja_id) ?? []), o]);
    return [...m.values()].sort((a, b) => Number(!a[0]!.seu_mercado) - Number(!b[0]!.seu_mercado) || a[0]!.distancia_km - b[0]!.distancia_km);
  }, [filtradas]);
  const pôr = (o: Oferta) => {
    adicionarProduto(o.produto);
    confirmar(`Na lista: ${o.produto.nome_curto ?? o.produto.nome}`);
  };

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 4 }]}>
      <ScrollView contentContainerStyle={estilos.conteudo} refreshControl={<RefreshControl refreshing={r.carregando && !!r.dados} onRefresh={r.atualizar} colors={[cor.estadoEconomia]} />}>
        <View style={{ gap: 4 }}>
          <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
            Ofertas reais
          </Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Só entra quando o preço caiu de verdade. Do mais perto para o mais longe.</Text>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={estilos.fileira} contentContainerStyle={estilos.chips}>
          <Chip texto="Perto de você" ativo={onde === "perto"} aoTocar={() => setOnde("perto")} />
          <Chip texto="Seu mercado" ativo={onde === "seu"} aoTocar={() => setOnde("seu")} />
          <Chip texto={`Da sua lista · ${minhas}`} ativo={onde === "lista"} aoTocar={() => setOnde("lista")} />
          <Chip texto="Todas" ativo={onde === "todas"} aoTocar={() => setOnde("todas")} />
        </ScrollView>
        {categorias.length > 1 ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={estilos.fileira} contentContainerStyle={estilos.chips}>
            <Chip texto="Tudo" ativo={!categoria} aoTocar={() => setCategoria(null)} />
            {categorias.map((c) => (
              <Chip key={c} texto={CATEGORIAS[c]!} ativo={categoria === c} aoTocar={() => setCategoria(categoria === c ? null : c)} />
            ))}
          </ScrollView>
        ) : null}

        {r.dados && !filtradas.length ? (
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
            {todas.length ? "Nenhuma oferta com esse filtro hoje." : "Nenhuma oferta real nos mercados perto de você hoje. O app confere todos os dias."}
          </Text>
        ) : null}

        {lojas.map((grupo, i) => {
          const loja = grupo[0]!;
          const longe = !loja.seu_mercado && loja.distancia_km > PERTO_KM;
          const primeiroLonge = longe && (i === 0 || !(!lojas[i - 1]![0]!.seu_mercado && lojas[i - 1]![0]!.distancia_km > PERTO_KM));
          const encarte = grupo.find((o) => o.fonte === "encarte" && o.valido_ate);
          return (
            <View key={loja.loja_id} style={{ gap: 10 }}>
              {primeiroLonge ? (
                <View style={{ gap: 2, paddingTop: 8 }}>
                  <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>Mais longe</Text>
                  <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Vale se você já for passar lá: uma oferta sozinha não paga a viagem.</Text>
                </View>
              ) : null}
              <View style={estilos.titulo}>
                <MarcaDaRede rede={loja.rede} tamanho={28} />
                <Text accessibilityRole="header" style={[fonte(longe ? "corpoForte" : "tituloSecao"), { color: cor.textoPrincipal, flex: 1 }]}>
                  {loja.nome} · {km(loja.distancia_km)}
                </Text>
                <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>
                  {grupo.length} {grupo.length === 1 ? "oferta" : "ofertas"}
                </Text>
              </View>
              {loja.seu_mercado || encarte ? (
                <Text style={[fonte("legenda"), { color: loja.seu_mercado ? cor.estadoEconomia : cor.textoSuave, marginTop: -6 }]}>
                  {loja.seu_mercado ? "Seu mercado" : ""}
                  {loja.seu_mercado && encarte ? " · " : ""}
                  {encarte ? `Encarte até ${new Date(encarte.valido_ate!).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}. Preço de clube vale com o cartão.` : ""}
                </Text>
              ) : null}
              {pares(grupo).map((par) => (
                <View key={par.map((o) => o.produto.id).join("-")} style={estilos.duas}>
                  {par.map((o) => (
                    <CartaoDeOferta
                      key={o.produto.id}
                      oferta={o}
                      aoTocar={() => router.push({ pathname: "/produto/[id]", params: { id: o.produto.id } })}
                      aoPor={() => pôr(o)}
                    />
                  ))}
                  {par.length === 1 ? <View style={{ flex: 1 }} /> : null}
                </View>
              ))}
            </View>
          );
        })}

        <View style={[estilos.promo, { backgroundColor: cor.fundoProfundo }]}>
          <View style={[estilos.sino, { backgroundColor: cor.marcaEtiqueta }]}>
            <Icone nome="aviso" cor={cor.marcaSobreEtiqueta} tamanho={20} />
          </View>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={[fonte("tituloSecao"), { color: cor.textoInverso }]}>Toda quinta, suas ofertas</Text>
            <Text style={[fonte("legenda"), { color: cor.textoInverso }]}>Um aviso por semana com as ofertas reais dos itens da sua lista.</Text>
          </View>
          <ChaveDoAviso ligado={aviso.ligado} aoMudar={(v) => void aviso.alternar(v)} inverso />
        </View>
        <View style={[estilos.nota, { backgroundColor: cor.fundoAfundado }]}>
          <Icone nome="info" cor={cor.textoPrincipal} tamanho={20} />
          <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>
            Oferta real = pelo menos 5% abaixo da mediana dos últimos 30 dias na mesma loja. Até completar 30 dias de histórico, vale o desconto
            anunciado, desde que o preço não fique acima do das outras lojas. No encarte, entra o que sai mais barato que em todos os outros mercados.
          </Text>
        </View>
      </ScrollView>
      <ExplicacaoDosAvisos visivel={aviso.explicando} aoPermitir={() => void aviso.ligar()} aoFechar={aviso.fecharExplicacao} />
    </View>
  );
}

function pares<T>(lista: T[]): T[][] {
  const saida: T[][] = [];
  for (let i = 0; i < lista.length; i += 2) saida.push(lista.slice(i, i + 2));
  return saida;
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 14 },
  // A fileira corre até a borda da tela (sai da margem de 20) e o primeiro chip fica alinhado ao conteúdo.
  chips: { gap: 8, paddingHorizontal: 20 },
  fileira: { marginHorizontal: -20 },
  titulo: { flexDirection: "row", alignItems: "center", gap: 8 },
  duas: { flexDirection: "row", gap: 12 },
  promo: { flexDirection: "row", alignItems: "center", borderRadius: 18, padding: 16, gap: 12, marginTop: 8 },
  sino: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  nota: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12 },
});
