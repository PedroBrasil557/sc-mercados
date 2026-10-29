/** 17 Fora da soma e 18 Outras lojas da rede (painéis da tela Comparar). */
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { api, type Comparacao, type LojaDaRede } from "@/api/cliente";
import { diferenca, km, reais } from "@/formatar";
import { escolherLoja } from "@/lista/comparacao";
import { type ItemVisivel } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Icone } from "./Icone";
import { PainelInferior } from "./PainelInferior";

const CUSTO_KM_CENTAVOS = 90; // R8: o mesmo padrão da API
const FOLGA_CENTAVOS = 1000; // R8: precisa sobrar 10 reais além do deslocamento

export function PainelForaDaSoma({ visivel, aoFechar, comparacao, itens }: { visivel: boolean; aoFechar: () => void; comparacao: Comparacao; itens: ItemVisivel[] }) {
  const { cor } = useTema();
  const nomes = new Map(itens.map((i) => [i.produto_id, i.nome]));
  const faltaEm = new Map<string, string[]>();
  for (const l of comparacao.lojas) for (const p of l.fora_da_soma) faltaEm.set(p, [...(faltaEm.get(p) ?? []), l.nome]);
  const n = faltaEm.size;
  return (
    <PainelInferior
      visivel={visivel}
      titulo={`${n} ${n === 1 ? "item fora da soma" : "itens fora da soma"}`}
      aoFechar={aoFechar}
      rodape={<Botao rotulo="Entendi" largo aoTocar={aoFechar} />}
    >
      <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
        Para comparar de forma justa, só somamos o que os {comparacao.lojas.length} mercados vendem hoje.
      </Text>
      {[...faltaEm.entries()].map(([produto, lojas]) => (
        <View key={produto} style={[estilos.linha, { borderBottomColor: cor.bordaPadrao }]}>
          <View style={[estilos.circulo, { backgroundColor: cor.estadoAlertaSuave }]}>
            <Icone nome="loja" cor={cor.estadoAlerta} tamanho={20} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{nomes.get(produto) ?? "Item da lista"}</Text>
            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Não encontrado no {lojas.join(", ")}</Text>
          </View>
        </View>
      ))}
    </PainelInferior>
  );
}

type PropsOutras = {
  rede: string | null;
  lojaAtual: string | null;
  aoFechar: () => void;
  quantidades: Record<string, number>;
};

export function PainelOutrasLojas({ rede, lojaAtual, aoFechar, quantidades }: PropsOutras) {
  const { cor } = useTema();
  const [lojas, setLojas] = useState<LojaDaRede[] | null>(null);
  const [escolhida, setEscolhida] = useState<string | null>(lojaAtual);

  useEffect(() => {
    if (!rede) return;
    let valido = true;
    api
      .outrasLojas(rede, quantidades)
      .then((r) => valido && setLojas(r.lojas))
      .catch(() => valido && setLojas([]));
    return () => {
      valido = false;
    };
  }, [rede, quantidades]);

  const atual = lojas?.find((l) => l.loja_id === lojaAtual) ?? null;
  const completas = useMemo(() => (lojas ?? []).filter((l) => l.itens_com_preco === l.itens), [lojas]);
  // A loja completa mais barata que a atual, e se a volta a mais compensa (R8).
  const alternativa = atual
    ? completas.filter((l) => l.loja_id !== atual.loja_id && l.total_centavos < atual.total_centavos).sort((a, b) => a.total_centavos - b.total_centavos)[0]
    : undefined;
  const analise = (() => {
    if (!atual || !alternativa) return null;
    const economia = atual.total_centavos - alternativa.total_centavos;
    const kmExtra = Math.max(0, alternativa.distancia_km - atual.distancia_km);
    const compensa = economia > Math.round(kmExtra * 2 * CUSTO_KM_CENTAVOS) + FOLGA_CENTAVOS;
    const nome = alternativa.bairro ?? alternativa.nome;
    return kmExtra > 0
      ? `A ${nome} economiza ${reais(economia)}, mas fica ${km(kmExtra)} mais longe. ${compensa ? "Compensa." : "Não compensa."}`
      : `A ${nome} economiza ${reais(economia)} e não fica mais longe.`;
  })();
  const nomeEscolhida = lojas?.find((l) => l.loja_id === escolhida);

  return (
    <PainelInferior
      visivel={!!rede}
      titulo={`${rede ?? ""} em Blumenau`}
      aoFechar={aoFechar}
      rodape={
        <Botao
          largo
          rotulo={escolhida === lojaAtual || !nomeEscolhida ? `Manter ${atual?.bairro ?? atual?.nome ?? "esta loja"}` : `Usar ${nomeEscolhida.bairro ?? nomeEscolhida.nome}`}
          aoTocar={() => {
            if (rede && escolhida && escolhida !== lojaAtual) escolherLoja(rede, escolhida);
            aoFechar();
          }}
        />
      }
    >
      <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
        Mesma lista, preços de cada loja. As lojas da mesma rede nem sempre cobram igual.
      </Text>
      {!lojas ? (
        <ActivityIndicator color={cor.estadoEconomia} />
      ) : (
        lojas.map((l) => {
          const ativa = l.loja_id === escolhida;
          const incompleta = l.itens_com_preco < l.itens;
          return (
            <Pressable
              key={l.loja_id}
              accessibilityRole="radio"
              accessibilityState={{ checked: ativa, disabled: incompleta && l.itens_com_preco === 0 }}
              disabled={l.itens_com_preco === 0}
              onPress={() => setEscolhida(l.loja_id)}
              style={[estilos.linha, { borderBottomColor: cor.bordaPadrao }]}
            >
              <View style={[estilos.radio, { borderColor: ativa ? cor.estadoEconomia : cor.bordaForte }]}>
                {ativa ? <View style={[estilos.radioMiolo, { backgroundColor: cor.estadoEconomia }]} /> : null}
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{l.bairro ?? l.nome}</Text>
                <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
                  {km(l.distancia_km)}
                  {l.loja_id === lojaAtual ? " · sua loja" : ""}
                  {incompleta ? ` · preço de ${l.itens_com_preco} de ${l.itens} itens` : ""}
                </Text>
              </View>
              <View style={{ alignItems: "flex-end" }}>
                <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal }]}>{l.itens_com_preco ? reais(l.total_centavos) : "sem preço"}</Text>
                {atual && l.loja_id !== atual.loja_id && !incompleta && l.total_centavos !== atual.total_centavos ? (
                  <Text style={[fonte("legenda"), { color: l.total_centavos < atual.total_centavos ? cor.estadoEconomia : cor.textoSuave }]}>
                    {diferenca(l.total_centavos - atual.total_centavos)}
                  </Text>
                ) : null}
              </View>
            </Pressable>
          );
        })
      )}
      {analise ? (
        <View style={[estilos.info, { backgroundColor: cor.fundoAfundado }]}>
          <Icone nome="info" cor={cor.textoPrincipal} tamanho={20} />
          <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>{analise}</Text>
        </View>
      ) : null}
    </PainelInferior>
  );
}

const estilos = StyleSheet.create({
  linha: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 56, paddingVertical: 10, borderBottomWidth: 1 },
  circulo: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  radioMiolo: { width: 12, height: 12, borderRadius: 6 },
  info: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12 },
});
