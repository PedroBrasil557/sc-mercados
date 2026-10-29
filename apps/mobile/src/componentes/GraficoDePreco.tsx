import { useState } from "react";
import { type LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";

import { reais } from "@/formatar";
import { fonte, useTema } from "@/tema";

/** Preço ao longo dos dias, em degraus (o preço vale até mudar). Com 1 dia só, mostra o ponto e explica. */
export function GraficoDePreco({ pontos }: { pontos: { dia: string; preco_centavos: number }[] }) {
  const { cor } = useTema();
  const [largura, setLargura] = useState(0);
  const altura = 72;
  const valores = pontos.map((p) => p.preco_centavos);
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const y = (v: number) => (max === min ? altura / 2 : 6 + (1 - (v - min) / (max - min)) * (altura - 12));
  const passo = pontos.length > 1 ? largura / (pontos.length - 1) : 0;
  let caminho = "";
  pontos.forEach((p, i) => {
    const x = i * passo;
    caminho += i === 0 ? `M0 ${y(p.preco_centavos)}` : ` H${x} V${y(p.preco_centavos)}`;
  });
  if (pontos.length === 1) caminho = `M0 ${y(min)} H${largura}`;
  const ultimo = pontos[pontos.length - 1];

  return (
    <View
      accessible
      accessibilityLabel={`Preço nos últimos dias: menor ${reais(min)}, maior ${reais(max)}${ultimo ? `, hoje ${reais(ultimo.preco_centavos)}` : ""}`}
      onLayout={(e: LayoutChangeEvent) => setLargura(e.nativeEvent.layout.width)}
    >
      {largura ? (
        <Svg width={largura} height={altura}>
          <Path d={caminho} stroke={cor.estadoEconomia} strokeWidth={2.5} fill="none" strokeLinejoin="round" />
          {ultimo ? <Circle cx={pontos.length > 1 ? largura : largura} cy={y(ultimo.preco_centavos)} r={4} fill={cor.estadoEconomia} /> : null}
        </Svg>
      ) : (
        <View style={{ height: altura }} />
      )}
      <View style={estilos.legenda}>
        <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
          {pontos.length > 1 ? `menor ${reais(min)} · maior ${reais(max)}` : "O histórico começou em 28/10 e cresce a cada dia."}
        </Text>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  legenda: { paddingTop: 6 },
});
