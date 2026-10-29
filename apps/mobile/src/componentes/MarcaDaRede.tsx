import { Image, StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

// Logo de mercado é marca de terceiro: só aparece no teste (modo de desenvolvimento) e só com a imagem na
// pasta local assets/logos-teste, que fica fora do git. Sem ela, ou numa versão de loja, vale o monograma.
const LOGOS = require.context("../../assets/logos-teste", false, /\.png$/);
const ARQUIVO: Record<string, string> = {
  Giassi: "giassi",
  Cooper: "cooper",
  Angeloni: "angeloni",
  "Sam's Club": "sams",
  "Rede Top": "redetop",
  Komprão: "komprao",
  Bistek: "bistek",
  Atacadão: "atacadao",
  "Brasil Atacadista": "brasil",
  "Fort Atacadista": "fort",
};
const BRANCO = "#FFFFFF"; // os logos são feitos para fundo branco, também no tema escuro

function logo(rede: string): number | null {
  const arquivo = ARQUIVO[rede];
  if (!__DEV__ || !arquivo || !LOGOS.keys().includes(`./${arquivo}.png`)) return null;
  return LOGOS(`./${arquivo}.png`) as number;
}

type Props = { rede: string; tamanho?: number; fundo?: string };

/** A rede ao lado do nome: o logo (no teste) ou a inicial num quadrado, como no Figma. */
export function MarcaDaRede({ rede, tamanho = 40, fundo }: Props) {
  const { cor } = useTema();
  const imagem = logo(rede);
  const raio = Math.round(tamanho * 0.3);
  if (imagem !== null) {
    return (
      <View style={[estilos.placa, { width: Math.round(tamanho * 1.6), height: tamanho, borderRadius: raio, backgroundColor: BRANCO, borderColor: cor.bordaPadrao, padding: Math.max(2, Math.round(tamanho * 0.1)) }]}>
        <Image source={imagem} resizeMode="contain" style={estilos.imagem} accessibilityIgnoresInvertColors />
      </View>
    );
  }
  return (
    <View style={[estilos.placa, { width: tamanho, height: tamanho, borderRadius: raio, backgroundColor: fundo ?? cor.fundoAfundado, borderWidth: 0 }]}>
      <Text style={[fonte(tamanho >= 32 ? "numeroMonograma" : "corpoForte"), { color: cor.textoPrincipal }]}>{rede.charAt(0)}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  placa: { alignItems: "center", justifyContent: "center", borderWidth: 1, overflow: "hidden" },
  imagem: { width: "100%", height: "100%" },
});
