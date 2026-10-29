/** 05 Comparar: quanto fica a lista na loja mais perto de cada rede (R7, R8, R13, R14). */
import { router } from "expo-router";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { LinhaDeMercado } from "@/componentes/LinhaDeMercado";
import { SeloDeFonte } from "@/componentes/SeloDeFonte";
import { diferenca, km, reais, seloDeFonte } from "@/formatar";
import { useComparacao } from "@/lista/comparacao";
import { useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Comparar() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { itens } = useLista();
  const { dados, carregando, semConexao, calculadaEm, atualizar } = useComparacao();
  const aComprar = itens.filter((i) => !i.comprado);

  const cabecalho = (subtitulo: string | null, selo: string | null) => (
    <View style={estilos.cabecalho}>
      <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
        Comparar
      </Text>
      {subtitulo ? <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>{subtitulo}</Text> : null}
      {selo ? <SeloDeFonte texto={selo} /> : null}
    </View>
  );

  if (!aComprar.length) {
    return (
      <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 4 }]}>
        {cabecalho(null, null)}
        <View style={estilos.vazio}>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
            Ponha na lista o que falta em casa e veja quanto fica em cada mercado perto de você.
          </Text>
          <Botao rotulo="Montar a lista" aoTocar={() => router.navigate("/lista")} largo />
        </View>
      </View>
    );
  }

  if (!dados) {
    return (
      <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 4 }]}>
        {cabecalho(null, null)}
        <View style={estilos.vazio}>
          {carregando ? <ActivityIndicator color={cor.estadoEconomia} /> : null}
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
            {semConexao ? "Sem internet. Assim que a conexão voltar, a comparação aparece aqui." : "Calculando quanto fica em cada mercado…"}
          </Text>
        </View>
      </View>
    );
  }

  const lojas = dados.lojas;
  const maisBarata = lojas[0];
  const maisCara = lojas[lojas.length - 1];
  const foraDaSoma = dados.itens - dados.comuns;
  const nomeDaRede = (id: string) => lojas.find((l) => l.loja_id === id)?.rede ?? "";
  const subtitulo = lojas.length
    ? `${dados.comuns} ${dados.comuns === 1 ? "item vendido" : "itens vendidos"} nas ${lojas.length} redes, na loja mais perto de você`
    : "Ainda não temos preço dos seus itens nas lojas perto de você";
  const selo = maisBarata?.preco_mais_antigo_em ? `${seloDeFonte("site", maisBarata.preco_mais_antigo_em)} · SEM TAXA` : null;

  return (
    <ScrollView
      style={{ backgroundColor: cor.fundoTela }}
      contentContainerStyle={[estilos.conteudo, { paddingTop: margem.top + 4 }]}
      refreshControl={<RefreshControl refreshing={carregando} onRefresh={atualizar} colors={[cor.estadoEconomia]} />}
    >
      {cabecalho(subtitulo, selo)}

      {semConexao && calculadaEm ? (
        <View style={[estilos.aviso, { backgroundColor: cor.fundoAfundado }]}>
          <Icone nome="sem-internet" cor={cor.textoPrincipal} tamanho={20} />
          <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>
            Sem internet: esta é a comparação das{" "}
            {new Date(calculadaEm).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}.
          </Text>
        </View>
      ) : null}

      {lojas.map((l, i) => (
        <LinhaDeMercado
          key={l.loja_id}
          rede={l.rede}
          detalhe={`${l.bairro ?? l.nome} · ${km(l.distancia_km)}`}
          total={reais(l.total_centavos)}
          destaque={i === 0 && lojas.length > 1}
          diferenca={
            i === 0
              ? lojas.length > 1 && maisCara && maisCara.total_centavos > l.total_centavos
                ? `${reais(maisCara.total_centavos - l.total_centavos)} a menos`
                : undefined
              : maisBarata
                ? diferenca(l.total_centavos - maisBarata.total_centavos)
                : undefined
          }
        />
      ))}

      {dados.redes_sem_preco.slice(0, 2).map((r) => (
        <View key={r.rede} style={[estilos.emBreve, { borderColor: cor.bordaPadrao }]}>
          <View style={[estilos.monograma, { backgroundColor: cor.fundoAfundado }]}>
            <Text style={[fonte("precoMedio"), { color: cor.textoSuave }]}>{r.rede.charAt(0)}</Text>
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={[fonte("corpoForte"), { color: cor.textoSuave }]}>{r.rede}</Text>
            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Em breve: preços pelos cupons que você lê</Text>
          </View>
        </View>
      ))}

      {dados.divisao && dados.divisao.economia_centavos > 0 ? (
        <View style={[estilos.cartao, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
          <View style={estilos.titulo}>
            <Icone nome="rota" cor={cor.estadoEconomia} />
            <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>Dividir a compra</Text>
          </View>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
            Comprando cada item onde é mais barato, entre {nomeDaRede(dados.divisao.lojas[0])} e {nomeDaRede(dados.divisao.lojas[1])}:
          </Text>
          <View style={estilos.valores}>
            <Text style={[fonte("precoGrande"), { color: cor.textoPrincipal }]}>{reais(dados.divisao.total_centavos)}</Text>
            <Text style={[fonte("corpoForte"), { color: cor.estadoEconomia }]}>{diferenca(-dados.divisao.economia_centavos)}</Text>
          </View>
          <View style={[estilos.valeAPena, { backgroundColor: dados.divisao.compensa ? cor.estadoEconomiaSuave : cor.fundoAfundado }]}>
            <Icone nome="info" cor={cor.textoPrincipal} tamanho={20} />
            <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>
              {dados.divisao.compensa ? "Compensa" : "Não compensa"}: a volta extra (~{km(dados.divisao.distancia_extra_km)}) custa cerca de{" "}
              {reais(dados.divisao.custo_deslocamento_centavos)}
            </Text>
          </View>
        </View>
      ) : null}

      {foraDaSoma > 0 ? (
        <View
          accessible
          accessibilityRole="text"
          accessibilityLabel={`${foraDaSoma} ${foraDaSoma === 1 ? "item fora da soma" : "itens fora da soma"}: não são vendidos em todas as lojas comparadas`}
          style={[estilos.fora, { backgroundColor: cor.fundoSuperficie }]}
        >
          <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal, flex: 1 }]}>
            {foraDaSoma} {foraDaSoma === 1 ? "item fora da soma" : "itens fora da soma"}
          </Text>
          <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>não vendidos em todas</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 12 },
  cabecalho: { gap: 4, paddingBottom: 4, paddingHorizontal: 0 },
  vazio: { padding: 20, gap: 16 },
  aviso: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12 },
  emBreve: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 16, borderWidth: 1.5, borderStyle: "dashed" },
  monograma: { width: 40, height: 40, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  cartao: { padding: 16, borderRadius: 20, borderWidth: 1, gap: 8 },
  titulo: { flexDirection: "row", alignItems: "center", gap: 8 },
  valores: { flexDirection: "row", alignItems: "baseline", gap: 12 },
  valeAPena: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  fora: { flexDirection: "row", alignItems: "center", gap: 12, padding: 16, borderRadius: 16 },
});
