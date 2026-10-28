import type { TabTriggerSlotProps } from "expo-router/ui";
import type { ComponentRef, Ref } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { fonte, useTema } from "@/tema";

import { Icone, type NomeIcone } from "./Icone";

type Props = TabTriggerSlotProps & { icone: NomeIcone; rotulo: string; ref?: Ref<ComponentRef<typeof Pressable>> };

/** Botão da barra inferior: a aba ativa ganha a pílula amarela da etiqueta atrás do ícone. */
export function BotaoDeAba({ icone, rotulo, isFocused, ref, ...props }: Props) {
  const { cor, medida } = useTema();
  return (
    <Pressable
      {...props}
      ref={ref}
      accessibilityRole="tab"
      accessibilityState={{ selected: !!isFocused }}
      accessibilityLabel={rotulo}
      style={estilos.botao}
    >
      <View
        style={[
          estilos.pilula,
          { borderRadius: medida.raioPilula },
          isFocused && { backgroundColor: cor.marcaEtiqueta },
        ]}
      >
        <Icone nome={icone} cor={isFocused ? cor.marcaSobreEtiqueta : cor.textoSuave} />
      </View>
      <Text
        numberOfLines={1}
        style={[fonte(isFocused ? "navegacaoAtivo" : "navegacaoRotulo"), { color: isFocused ? cor.textoPrincipal : cor.textoSuave }]}
      >
        {rotulo}
      </Text>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  botao: { flex: 1, alignItems: "center", gap: 4, minHeight: 56, paddingTop: 8, paddingBottom: 6 },
  pilula: { width: 56, height: 32, alignItems: "center", justifyContent: "center" },
});
