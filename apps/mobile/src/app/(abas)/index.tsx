/** 02 Início (e 15 Início · primeiro uso, com a lista de exemplo). */
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Comparacao, type Produto } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { CartaoDaLista } from "@/componentes/CartaoDaLista";
import { Icone } from "@/componentes/Icone";
import { SeletorDeBairro } from "@/componentes/SeletorDeBairro";
import * as armazem from "@/lista/armazem";
import { useComparacao } from "@/lista/comparacao";
import { adicionarProduto, buscarProdutos, trocarBairro, useLista } from "@/lista/sincronia";
import { reais } from "@/formatar";
import { fonte, useTema } from "@/tema";

// Rancho comum de Blumenau (as cestas validadas na coleta de 22/10/2026), pelo começo do nome no catálogo.
const EXEMPLO = ["Arroz", "Feijão carioca", "Café", "Óleo", "Açúcar", "Leite integral", "Macarrão", "Molho de tomate", "Margarina",
  "Creme dental", "Papel higiênico", "Detergente", "Sabão em pó"];
const CHAVE_EXEMPLO_DISPENSADO = "exemplo_dispensado";

function saudacao(agora = new Date()): string {
  const h = agora.getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

export default function Inicio() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao, itens } = useLista();
  const comparacao = useComparacao();
  const [escolhendoBairro, setEscolhendoBairro] = useState(false);
  const [dispensado, setDispensado] = useState(() => armazem.lerGuardado<boolean>(CHAVE_EXEMPLO_DISPENSADO) ?? false);
  const aComprar = itens.filter((i) => !i.comprado);
  const primeiroUso = !aComprar.length && !dispensado;
  const exemplo = useExemplo(primeiroUso ? (sessao?.bairro_id ?? null) : null);
  const membros = sessao ? Object.values(sessao.nomes) : [];
  const economia = useEconomiaDoMes();

  function usarExemplo() {
    if (!exemplo) return;
    exemplo.produtos.forEach(adicionarProduto);
    router.navigate("/lista");
  }

  function comecarDoZero() {
    armazem.guardar(CHAVE_EXEMPLO_DISPENSADO, true);
    setDispensado(true);
    router.navigate("/lista");
  }

  return (
    <ScrollView style={{ backgroundColor: cor.fundoTela }} contentContainerStyle={[estilos.conteudo, { paddingTop: margem.top + 4 }]}>
      <View style={estilos.cabecalho}>
        <View style={{ flex: 1 }}>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>{primeiroUso ? "Olá! Mercados perto de" : saudacao()}</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Bairro: ${sessao?.bairro_nome ?? "não escolhido"}. Toque para trocar`}
            onPress={() => setEscolhendoBairro(true)}
            style={estilos.bairro}
          >
            <Text numberOfLines={1} style={[fonte("tituloTela"), { color: cor.textoPrincipal, flexShrink: 1 }]}>
              {sessao?.bairro_nome ?? "Escolha o bairro"}
            </Text>
            <View style={{ transform: [{ rotate: "90deg" }] }}>
              <Icone nome="seta-direita" cor={cor.textoPrincipal} tamanho={20} />
            </View>
          </Pressable>
        </View>
        <View style={estilos.casa} accessible accessibilityLabel={`Casa: ${membros.join(", ")}`}>
          {membros.slice(0, 3).map((nome, i) => (
            <View
              key={`${nome}-${i}`}
              style={[
                estilos.membro,
                { backgroundColor: i === 0 ? cor.marcaEtiqueta : cor.estadoEconomiaSuave, borderColor: cor.fundoTela, marginLeft: i ? -10 : 0 },
              ]}
            >
              <Text style={[fonte("corpoForte"), { color: i === 0 ? cor.marcaSobreEtiqueta : cor.textoPrincipal }]}>
                {nome.charAt(0).toUpperCase()}
              </Text>
            </View>
          ))}
        </View>
      </View>

      {!sessao?.bairro_id ? (
        <View style={[estilos.exemplo, { backgroundColor: cor.marcaEtiqueta }]}>
          <Text style={[fonte("tituloSecao"), { color: cor.marcaSobreEtiqueta }]}>Onde você mora?</Text>
          <Text style={[fonte("corpoMenor"), { color: cor.marcaSobreEtiqueta }]}>
            Com o bairro, o app compara a lista na loja mais perto de você em cada rede.
          </Text>
          <Botao rotulo="Escolher o bairro" largo aoTocar={() => setEscolhendoBairro(true)} />
        </View>
      ) : primeiroUso ? (
        <>
          <View style={[estilos.exemplo, { backgroundColor: cor.marcaEtiqueta }]}>
            <Text style={[fonte("tituloSecao"), { color: cor.marcaSobreEtiqueta }]}>Lista de exemplo</Text>
            <Text style={[fonte("corpoMenor"), { color: cor.marcaSobreEtiqueta }]}>
              São {EXEMPLO.length} itens comuns no rancho de Blumenau. Troque pelo que você compra de verdade.
            </Text>
            <Botao rotulo="Usar esta lista" largo desativado={!exemplo} aoTocar={usarExemplo} />
            <Botao rotulo="Começar do zero" tipo="contorno" largo aoTocar={comecarDoZero} />
          </View>
          {exemplo?.comparacao ? (
            <CartaoDaLista
              rotulo={`Lista de exemplo · ${EXEMPLO.length} itens`}
              comparacao={exemplo.comparacao}
              aoComparar={() => Alert.alert("Lista de exemplo", "Use esta lista para ver a comparação completa, item por item.")}
            />
          ) : (
            <ActivityIndicator color={cor.estadoEconomia} style={{ padding: 24 }} />
          )}
        </>
      ) : comparacao.dados?.lojas.length ? (
        <CartaoDaLista
          rotulo={`Sua lista da semana · ${aComprar.length} ${aComprar.length === 1 ? "item" : "itens"}`}
          comparacao={comparacao.dados}
          aoComparar={() => router.navigate("/comparar")}
        />
      ) : aComprar.length ? (
        <View style={[estilos.aviso, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
          {comparacao.carregando ? <ActivityIndicator color={cor.estadoEconomia} /> : null}
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, flex: 1 }]}>
            {comparacao.semConexao ? "Sem internet: a comparação aparece quando a conexão voltar." : "Calculando quanto fica a sua lista…"}
          </Text>
        </View>
      ) : (
        <View style={[estilos.exemplo, { backgroundColor: cor.fundoSuperficie, borderWidth: 1, borderColor: cor.bordaPadrao }]}>
          <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>Lista em dia</Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Quando faltar alguma coisa em casa, anote na lista.</Text>
          <Botao rotulo="Abrir a lista" largo aoTocar={() => router.navigate("/lista")} />
        </View>
      )}

      {sessao?.bairro_id && !primeiroUso ? (
        <View style={estilos.acoes}>
          <View style={{ flex: 1 }}>
            <Botao
              rotulo="Estou no mercado"
              tipo="etiqueta"
              largo
              aoTocar={() =>
                router.push({ pathname: "/no-mercado", params: comparacao.dados?.lojas[0] ? { loja: comparacao.dados.lojas[0].loja_id } : {} })
              }
            />
          </View>
          <Botao rotulo="Ler cupom" tipo="contorno" aoTocar={() => router.push("/ler-cupom")} />
        </View>
      ) : null}

      {economia && economia.cupons > 0 ? (
        <View style={[estilos.economia, { backgroundColor: cor.estadoEconomiaSuave }]}>
          <View style={[estilos.brilho, { backgroundColor: cor.fundoSuperficie }]}>
            <Icone nome="brilho" cor={cor.estadoEconomia} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={[fonte("corpoMenor"), { color: cor.textoPrincipal }]}>
              Sua economia em {new Date(`${economia.mes}T12:00:00`).toLocaleDateString("pt-BR", { month: "long" })}
            </Text>
            <Text style={[fonte("precoMedio"), { color: cor.estadoEconomia }]}>{reais(economia.economia_centavos)}</Text>
            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
              vs. média dos mercados · {economia.cupons} {economia.cupons === 1 ? "cupom lido" : "cupons lidos"}
            </Text>
          </View>
        </View>
      ) : null}

      <SeletorDeBairro
        visivel={escolhendoBairro}
        selecionado={sessao?.bairro_id ?? null}
        aoFechar={() => setEscolhendoBairro(false)}
        aoConfirmar={(b) => {
          setEscolhendoBairro(false);
          trocarBairro(b).catch(() => Alert.alert("Sem internet", "Não deu para trocar o bairro agora. Tente de novo em instantes."));
        }}
      />
    </ScrollView>
  );
}

/** Economia do mês (R12), somada dos cupons lidos pela casa. */
function useEconomiaDoMes() {
  const [economia, setEconomia] = useState<{ mes: string; economia_centavos: number; cupons: number } | null>(
    () => armazem.lerGuardado("economia_mes"),
  );
  useEffect(() => {
    let valido = true;
    api
      .economia()
      .then((e) => {
        armazem.guardar("economia_mes", e);
        if (valido) setEconomia(e);
      })
      .catch(() => undefined);
    return () => {
      valido = false;
    };
  }, []);
  return economia;
}

/** Lista de exemplo já com os preços de hoje no bairro, antes de a família decidir usá-la. */
function useExemplo(bairroId: string | null): { produtos: Produto[]; comparacao: Comparacao | null } | null {
  const [exemplo, setExemplo] = useState<{ produtos: Produto[]; comparacao: Comparacao | null } | null>(null);
  useEffect(() => {
    if (!bairroId) return;
    let valido = true;
    void (async () => {
      const { produtos } = await buscarProdutos("");
      const escolhidos = EXEMPLO.map((nome) => produtos.find((p) => p.nome.startsWith(nome))).filter((p): p is Produto => !!p);
      const itens = Object.fromEntries(escolhidos.map((p) => [p.id, 1]));
      const comparacao = escolhidos.length ? await api.comparar(bairroId, itens).catch(() => null) : null;
      if (valido) setExemplo({ produtos: escolhidos, comparacao });
    })();
    return () => {
      valido = false;
    };
  }, [bairroId]);
  return exemplo;
}

const estilos = StyleSheet.create({
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 20 },
  cabecalho: { flexDirection: "row", alignItems: "center", gap: 12, paddingTop: 4 },
  bairro: { flexDirection: "row", alignItems: "center", gap: 4, minHeight: 36, alignSelf: "flex-start" },
  casa: { flexDirection: "row" },
  membro: { width: 44, height: 44, borderRadius: 22, borderWidth: 2.5, alignItems: "center", justifyContent: "center" },
  exemplo: { borderRadius: 24, padding: 20, gap: 12 },
  aviso: { flexDirection: "row", alignItems: "center", gap: 12, padding: 16, borderRadius: 16, borderWidth: 1 },
  acoes: { flexDirection: "row", gap: 12 },
  economia: { flexDirection: "row", alignItems: "center", gap: 16, padding: 16, borderRadius: 20 },
  brilho: { width: 44, height: 44, borderRadius: 14, alignItems: "center", justifyContent: "center" },
});
