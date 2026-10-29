import { Pressable, StyleSheet, Text, View } from "react-native";

import { quantidade as formatarQuantidade, tamanho as formatarTamanho } from "@/formatar";
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
};

/** Figma "Item da lista": miniatura P, nome em até 2 linhas, detalhe em 1, e a quantidade com −/+ de 40 dp. */
export function ItemDaLista({ item, meuNome, aoSomar, aoTirar, aoTocar, aoSegurar }: Props) {
  const { cor } = useTema();
  const quem = item.adicionado_por === meuNome ? "você" : item.adicionado_por;
  const detalhe = [item.marca, quem].filter(Boolean).join(" · ");
  const qtd = formatarQuantidade(item.quantidade);
  return (
    <View style={[estilos.item, { borderBottomColor: cor.bordaPadrao }]}>
      <Pressable
        style={estilos.toque}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: item.comprado }}
        accessibilityLabel={`${item.nome}, quantidade ${qtd}${item.comprado ? ", já comprado" : ""}`}
        accessibilityHint="Toque para marcar como comprado. Toque e segure para tirar da lista."
        onPress={aoTocar}
        onLongPress={aoSegurar}
      >
        <Miniatura categoria={item.categoria} tamanho={formatarTamanho(item.tamanho, item.unidade)} nome={item.nome} />
        <View style={estilos.texto}>
          <Text
            numberOfLines={2}
            style={[fonte("corpoForte"), { color: item.comprado ? cor.textoSuave : cor.textoPrincipal }, item.comprado && estilos.riscado]}
          >
            {item.nome}
          </Text>
          {item.aviso ? (
            <Text numberOfLines={1} style={[fonte("legenda"), { color: cor.estadoAlerta }]}>
              {item.aviso}
            </Text>
          ) : detalhe ? (
            <Text numberOfLines={1} style={[fonte("legenda"), { color: quem && quem !== "você" ? cor.estadoEconomia : cor.textoSuave }]}>
              {detalhe}
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
      hitSlop={4}
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
  botao: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  numero: { width: 32, textAlign: "center" },
});
