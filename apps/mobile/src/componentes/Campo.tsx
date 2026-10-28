import { StyleSheet, TextInput, type TextInputProps } from "react-native";

import { fonte, useTema } from "@/tema";

/** Campo de texto com as cores do tema. `rotulo` vira o nome lido pelo leitor de tela. */
export function Campo({ rotulo, style, ...props }: TextInputProps & { rotulo: string }) {
  const { cor, medida } = useTema();
  return (
    <TextInput
      accessibilityLabel={rotulo}
      placeholderTextColor={cor.textoSuave}
      selectionColor={cor.estadoEconomia}
      style={[
        fonte("corpoPadrao"),
        estilos.campo,
        { color: cor.textoPrincipal, backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderRadius: medida.raioMedio },
        style,
      ]}
      {...props}
    />
  );
}

const estilos = StyleSheet.create({
  campo: { minHeight: 48, paddingHorizontal: 14, borderWidth: 1 },
});
