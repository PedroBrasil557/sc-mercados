/** R7 Comparar: a recomendação com o porquê, o total de cada mercado já com a ida e volta (R8), dividir a compra,
 * o que pegar nos itens "qualquer marca" e as lojas com só alguns itens (R7, R13, R14). */
import { router } from "expo-router";
import { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { MarcaDaRede } from "@/componentes/MarcaDaRede";
import { Botao } from "@/componentes/Botao";
import { Icone } from "@/componentes/Icone";
import { LinhaDeMercado } from "@/componentes/LinhaDeMercado";
import { PainelForaDaSoma, PainelOutrasLojas } from "@/componentes/PaineisDaComparacao";
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
  const [redeAberta, setRedeAberta] = useState<{ rede: string; loja: string } | null>(null);
  const [foraAberto, setForaAberto] = useState(false);
  const quantidades = useMemo(() => {
    const q: Record<string, number> = {};
    for (const i of itens) if (i.produto_id && !i.comprado) q[i.produto_id] = (q[i.produto_id] ?? 0) + i.quantidade;
    return q;
  }, [itens]);

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
  // A API manda a recomendada primeiro (a mais perto, a não ser que outra pague a viagem e sobre 10 reais).
  const maisBarata = lojas[0];
  const menorPrateleira = Math.min(...lojas.map((l) => l.total_centavos));
  const etiqueta = maisBarata && maisBarata.total_centavos <= menorPrateleira ? "Mais barato" : "Melhor para você";
  const poucos = dados.lojas_com_poucos_itens ?? [];
  const foraDaSoma = dados.itens - dados.comuns;
  const nomeDaRede = (id: string) => lojas.find((l) => l.loja_id === id)?.rede ?? "";
  const subtitulo = lojas.length
    ? `Sua lista (${dados.itens} ${dados.itens === 1 ? "item" : "itens"}) nos mercados perto de você${dados.comuns < dados.itens ? ` · ${dados.comuns} em todos` : ""}`
    : "Ainda não temos preço dos seus itens nas lojas perto de você";
  const barata = lojas.length ? lojas.reduce((a, b) => (b.total_centavos < a.total_centavos ? b : a)) : null;
  const porque = !maisBarata
    ? ""
    : barata && barata.loja_id !== maisBarata.loja_id
      ? `${maisBarata.seu_mercado ? "É o seu mercado" : "É o mais perto"}. O ${barata.rede} sai ${reais(maisBarata.total_centavos - barata.total_centavos)} mais barato na prateleira, mas a ida e volta a mais custa cerca de ${reais(Math.max(0, barata.custo_viagem_centavos - maisBarata.custo_viagem_centavos))}.`
      : lojas.length > 1
        ? `É o mais barato hoje${maisBarata.seu_mercado ? " e é o seu mercado" : ""}.`
        : "É o único com preço de todos os itens por enquanto.";
  const escolhas = maisBarata?.escolhas ?? [];
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

      {maisBarata && lojas.length ? (
        <View style={[estilos.melhor, { backgroundColor: cor.fundoProfundo }]}>
          <Text style={[fonte("rotulo"), { color: cor.marcaEtiqueta }]}>MELHOR PARA VOCÊ</Text>
          <Text style={[fonte("tituloTela"), { color: cor.textoInverso }]}>{maisBarata.nome}</Text>
          <View style={estilos.valores}>
            <Text style={[fonte("precoGrande"), { color: cor.textoInverso }]}>{reais(maisBarata.total_centavos)}</Text>
            <Text style={[fonte("corpoMenor"), { color: cor.textoInverso }]}>
              {km(maisBarata.distancia_km)}
              {maisBarata.seu_mercado ? " · seu mercado" : ""}
            </Text>
          </View>
          {maisBarata.custo_viagem_centavos ? (
            <Text style={[fonte("corpoMenor"), { color: cor.textoInverso, opacity: 0.85 }]}>
              + {reais(maisBarata.custo_viagem_centavos)} de ida e volta = {reais(maisBarata.total_com_viagem_centavos ?? maisBarata.total_centavos)}
            </Text>
          ) : null}
          <View style={[estilos.divisor, { backgroundColor: cor.sobreposicaoDivisor }]} />
          <Text style={[fonte("corpoMenor"), { color: cor.textoInverso, opacity: 0.9 }]}>{porque}</Text>
          {escolhas.length ? (
            <Text style={[fonte("legenda"), { color: cor.textoInverso, opacity: 0.8 }]}>
              Qualquer marca: pegue {escolhas.map((e) => e.marca).filter(Boolean).slice(0, 3).join(", ")}
              {escolhas.length > 3 ? ` e mais ${escolhas.length - 3}` : ""}
            </Text>
          ) : null}
        </View>
      ) : null}

      {lojas.length > 1 ? (
        <Text accessibilityRole="header" style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>
          Total com a ida e volta
        </Text>
      ) : null}
      {lojas.map((l, i) => (
        <LinhaDeMercado
          key={l.loja_id}
          rede={l.rede}
          detalhe={`${l.bairro ?? l.nome} · ${km(l.distancia_km)}${l.custo_viagem_centavos ? `\n${reais(l.total_centavos)} + ${reais(l.custo_viagem_centavos)} de ida e volta` : ""}`}
          total={reais(l.total_com_viagem_centavos ?? l.total_centavos)}
          destaque={i === 0 && lojas.length > 1}
          etiqueta={etiqueta}
          nota={l.nota}
          aoTocar={() => setRedeAberta({ rede: l.rede, loja: l.loja_id })}
          diferenca={
            i === 0 || !maisBarata
              ? undefined
              : diferenca((l.total_com_viagem_centavos ?? l.total_centavos) - (maisBarata.total_com_viagem_centavos ?? maisBarata.total_centavos))
          }
        />
      ))}

      {poucos.length ? (
        <Text accessibilityRole="header" style={[fonte("rotulo"), { color: cor.textoSuave, paddingTop: 8 }]}>
          Só alguns itens da sua lista
        </Text>
      ) : null}
      {poucos.map((l) => {
        const n = l.itens.length;
        const economia = l.mesmos_itens_na_recomendada_centavos - l.mesmos_itens_aqui_centavos;
        const validade = l.valido_ate
          ? `Encarte até ${new Date(l.valido_ate).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}. `
          : "";
        const comparado =
          l.mesmos_itens && maisBarata && economia !== 0
            ? `${l.mesmos_itens === n ? "Esses itens" : `${l.mesmos_itens} desses itens`} saem ${reais(Math.abs(economia))} ${economia > 0 ? "a menos" : "a mais"} que no ${maisBarata.rede}.`
            : "";
        return (
          <LinhaDeMercado
            key={l.loja_id}
            rede={l.rede}
            detalhe={`${n} ${n === 1 ? "item" : "itens"} · ${l.bairro ?? l.nome} · ${km(l.distancia_km)}`}
            total={reais(l.total_centavos)}
            nota={`${validade}${comparado}`.trim() || null}
            aoTocar={() => setRedeAberta({ rede: l.rede, loja: l.loja_id })}
          />
        );
      })}

      {dados.redes_sem_preco.slice(0, 2).map((r) => (
        <View key={r.rede} style={[estilos.emBreve, { borderColor: cor.bordaPadrao }]}>
          <MarcaDaRede rede={r.rede} />
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
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${foraDaSoma} ${foraDaSoma === 1 ? "item fora da soma" : "itens fora da soma"}. Ver quais`}
          onPress={() => setForaAberto(true)}
          style={[estilos.fora, { backgroundColor: cor.fundoSuperficie }]}
        >
          <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal, flex: 1 }]}>
            {foraDaSoma} {foraDaSoma === 1 ? "item fora da soma" : "itens fora da soma"}
          </Text>
          <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>ver</Text>
          <Icone nome="seta-direita" cor={cor.estadoEconomia} tamanho={20} />
        </Pressable>
      ) : null}
      <PainelForaDaSoma visivel={foraAberto} aoFechar={() => setForaAberto(false)} comparacao={dados} itens={itens} />
      <PainelOutrasLojas
        key={redeAberta ? `${redeAberta.rede}-${redeAberta.loja}` : "fechado"}
        rede={redeAberta?.rede ?? null}
        lojaAtual={redeAberta?.loja ?? null}
        quantidades={quantidades}
        aoFechar={() => setRedeAberta(null)}
      />
    </ScrollView>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 12 },
  cabecalho: { gap: 4, paddingBottom: 4, paddingHorizontal: 0 },
  vazio: { padding: 20, gap: 16 },
  aviso: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12 },
  melhor: { borderRadius: 28, padding: 20, gap: 10 },
  divisor: { height: 1 },
  emBreve: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 16, borderWidth: 1.5, borderStyle: "dashed" },
  cartao: { padding: 16, borderRadius: 20, borderWidth: 1, gap: 8 },
  titulo: { flexDirection: "row", alignItems: "center", gap: 8 },
  valores: { flexDirection: "row", alignItems: "baseline", gap: 12 },
  valeAPena: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  fora: { flexDirection: "row", alignItems: "center", gap: 12, padding: 16, borderRadius: 16 },
});
