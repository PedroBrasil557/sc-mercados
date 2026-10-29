import { Pressable, StyleSheet, Text, View } from "react-native";

import { marca as marcaLegivel, quantidade as formatarQuantidade, reais, tamanho as formatarTamanho } from "@/formatar";
import type { ItemVisivel } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

import { Icone } from "./Icone";
import { Miniatura } from "./Miniatura";

type Props = {
  item: ItemVisivel;
  meuNome: string;
  aoSomar: () => void;
  aoTirar: () => void;
  aoTocar: () => void;
  aoSegurar: () => void;
  /** Preço no seu mercado: unitário (da marca pedida ou, em "qualquer marca", da mais barata de hoje). */
  preco?: { unitario: number; marcaDeHoje?: string | null } | null;
  /** Item que o seu mercado não vende (ex.: marca própria de outra rede). */
  semPrecoAqui?: boolean;
};

/** Figma "Item da lista": miniatura P, nome em até 2 linhas, detalhe em 1, e a quantidade com −/+ de 40 dp. */
export function ItemDaLista({ item, meuNome, aoSomar, aoTirar, aoTocar, aoSegurar, preco, semPrecoAqui }: Props) {
  const { cor } = useTema();
  const quem = item.adicionado_por === meuNome ? "você" : item.adicionado_por;
  const marca = item.qualquer_marca
    ? preco?.marcaDeHoje
      ? `Qualquer marca · hoje: ${marcaLegivel(preco.marcaDeHoje)}`
      : "Qualquer marca"
    : marcaLegivel(item.marca);
  const detalhe = semPrecoAqui
    ? `Não tem no seu mercado${item.qualquer_marca ? "" : " · trocar por qualquer marca?"}`
    : [marca, quem && quem !== "você" ? `${quem} pôs` : null].filter(Boolean).join(" · ");
  const qtd = formatarQuantidade(item.quantidade);
  const nome = item.nome_curto ?? item.nome;
  return (
    <View style={[estilos.item, { borderBottomColor: cor.bordaPadrao }]}>
      <Pressable
        style={estilos.toque}
        accessibilityRole="button"
        accessibilityLabel={`${nome}, ${detalhe}, quantidade ${qtd}${preco ? `, ${reais(preco.unitario * item.quantidade)} no seu mercado` : ""}${item.comprado ? ", já comprado" : ""}`}
        accessibilityHint="Toque para ver o preço em cada mercado. Toque e segure para tirar da lista."
        onPress={aoTocar}
        onLongPress={aoSegurar}
      >
        <Miniatura categoria={item.categoria} tamanho={formatarTamanho(item.tamanho, item.unidade)} nome={item.nome} />
        <View style={estilos.texto}>
          <Text
            numberOfLines={2}
            style={[fonte("corpoForte"), { color: item.comprado ? cor.textoSuave : cor.textoPrincipal }, item.comprado && estilos.riscado]}
          >
            {nome}
          </Text>
          {item.aviso ? (
            <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.estadoAlerta }]}>
              {item.aviso}
            </Text>
          ) : detalhe ? (
            <Text numberOfLines={2} style={[fonte("legenda"), { color: semPrecoAqui ? cor.estadoAlerta : cor.textoSuave }]}>
              {detalhe}
            </Text>
          ) : null}
          {preco ? (
            <Text numberOfLines={1} style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>
              {reais(preco.unitario * item.quantidade)}
              {item.quantidade !== 1 ? <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{`  ·  ${reais(preco.unitario)} cada`}</Text> : null}
            </Text>
          ) : null}
        </View>
      </Pressable>
      <View style={[estilos.quantidade, { backgroundColor: cor.fundoAfundado }]}>
        <BotaoQuantidade rotulo={`Tirar um de ${item.nome}`} icone="menos" aoTocar={aoTirar} />
        <Text accessibilityLiveRegion="polite" style={[fonte("numeroQuantidade"), estilos.numero, { color: cor.textoPrincipal }]}>
          {qtd}
        </Text>
        <BotaoQuantidade rotulo={`Somar um de ${item.nome}`} icone="mais" aoTocar={aoSomar} />
      </View>
    </View>
  );
}

function BotaoQuantidade({ rotulo, icone, aoTocar }: { rotulo: string; icone: "mais" | "menos"; aoTocar: () => void }) {
  const { cor } = useTema();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      hitSlop={6}
      onPress={aoTocar}
      style={({ pressed }) => [estilos.botao, { backgroundColor: pressed ? cor.fundoAfundado : cor.fundoSuperficie }]}
    >
      <Icone nome={icone} cor={cor.textoPrincipal} tamanho={20} />
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  item: { minHeight: 72, flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, borderBottomWidth: 1 },
  toque: { flex: 1, flexDirection: "row", alignItems: "center", gap: 12 },
  texto: { flex: 1, gap: 2 },
  riscado: { textDecorationLine: "line-through" },
  quantidade: { flexDirection: "row", alignItems: "center", gap: 2, padding: 4, borderRadius: 24 },
  botao: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  numero: { minWidth: 24, textAlign: "center" },
});
