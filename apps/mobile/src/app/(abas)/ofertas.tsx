/** 07 Ofertas reais (R9): só entra quando o preço caiu de verdade. */
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Oferta } from "@/api/cliente";
import { ChaveDoAviso, ExplicacaoDosAvisos, useAvisoDeQuinta } from "@/componentes/AvisoDeQuinta";
import { CartaoDeOferta } from "@/componentes/CartaoDeOferta";
import { Chip } from "@/componentes/Chip";
import { Icone } from "@/componentes/Icone";
import * as armazem from "@/lista/armazem";
import { useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

type Celula = { tipo: "oferta"; oferta: Oferta } | { tipo: "aviso" };

export default function Ofertas() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { itens } = useLista();
  const aviso = useAvisoDeQuinta();
  const [ofertas, setOfertas] = useState<Oferta[] | null>(() => armazem.lerGuardado<Oferta[]>("ofertas"));
  const [carregando, setCarregando] = useState(false);
  const [soDaLista, setSoDaLista] = useState(true);

  const buscar = useCallback(
    () =>
      api
        .ofertas()
        .then((r) => {
          armazem.guardar("ofertas", r.ofertas);
          setOfertas(r.ofertas);
        })
        .catch(() => undefined),
    [],
  );
  useEffect(() => {
    void buscar();
  }, [buscar]);
  const carregar = () => {
    setCarregando(true);
    void buscar().finally(() => setCarregando(false));
  };

  const daLista = new Set(itens.map((i) => i.produto_id));
  const todas = ofertas ?? [];
  const minhas = todas.filter((o) => daLista.has(o.produto.id));
  const mostrar = soDaLista && minhas.length ? minhas : todas;
  const celulas: Celula[] = [...mostrar.map((o) => ({ tipo: "oferta" as const, oferta: o })), { tipo: "aviso" as const }];

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 4 }]}>
      <FlatList
        data={celulas}
        numColumns={2}
        keyExtractor={(c) => (c.tipo === "aviso" ? "aviso" : `${c.oferta.produto.id}-${c.oferta.loja_id}`)}
        columnWrapperStyle={{ gap: 12 }}
        contentContainerStyle={estilos.conteudo}
        refreshControl={<RefreshControl refreshing={carregando} onRefresh={carregar} colors={[cor.estadoEconomia]} />}
        ListHeaderComponent={
          <View style={{ gap: 12, paddingBottom: 4 }}>
            <View style={{ gap: 4 }}>
              <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
                Ofertas reais
              </Text>
              <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Só entra quando o preço caiu de verdade</Text>
            </View>
            {todas.length ? (
              <View style={estilos.chips}>
                <Chip texto={`Da minha lista · ${minhas.length}`} ativo={soDaLista && minhas.length > 0} aoTocar={() => setSoDaLista(true)} />
                <Chip texto={`Todas · ${todas.length}`} ativo={!soDaLista || !minhas.length} aoTocar={() => setSoDaLista(false)} />
              </View>
            ) : ofertas ? (
              <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
                Nenhuma oferta real nos mercados perto de você hoje. O app confere todos os dias.
              </Text>
            ) : null}
          </View>
        }
        renderItem={({ item }) =>
          item.tipo === "oferta" ? (
            <CartaoDeOferta oferta={item.oferta} aoTocar={() => router.push({ pathname: "/produto/[id]", params: { id: item.oferta.produto.id } })} />
          ) : (
            <View style={[estilos.promo, { backgroundColor: cor.fundoProfundo }]}>
              <View style={[estilos.sino, { backgroundColor: cor.marcaEtiqueta }]}>
                <Icone nome="aviso" cor={cor.marcaSobreEtiqueta} tamanho={20} />
              </View>
              <Text style={[fonte("tituloSecao"), { color: cor.textoInverso }]}>Toda quinta, suas ofertas</Text>
              <Text style={[fonte("legenda"), { color: cor.textoInverso, flex: 1 }]}>Um aviso por semana com as ofertas reais dos itens da sua lista.</Text>
              <ChaveDoAviso ligado={aviso.ligado} aoMudar={(v) => void aviso.alternar(v)} inverso />
            </View>
          )
        }
        ListFooterComponent={
          <View style={[estilos.nota, { backgroundColor: cor.fundoAfundado }]}>
            <Icone nome="info" cor={cor.textoPrincipal} tamanho={20} />
            <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>
              Oferta real = pelo menos 5% abaixo da mediana dos últimos 30 dias na mesma loja. Até completar 30 dias de histórico (a coleta
              começou em 28/10), vale o desconto anunciado pela loja, desde que o preço não fique acima do das outras lojas.
            </Text>
          </View>
        }
      />
      <ExplicacaoDosAvisos visivel={aviso.explicando} aoPermitir={() => void aviso.ligar()} aoFechar={aviso.fecharExplicacao} />
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 12 },
  chips: { flexDirection: "row", gap: 8 },
  promo: { flex: 1, minHeight: 240, borderRadius: 18, padding: 16, gap: 10 },
  sino: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  nota: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12, marginTop: 4 },
});
