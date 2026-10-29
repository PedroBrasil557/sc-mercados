/**
 * Confirmação ao pôr algo na lista: um aviso curto no pé da tela, com vibração leve.
 * A animação dura 250 ms e não repete; com "reduzir movimento" ligado no celular, aparece parada.
 */
import * as Haptics from "expo-haptics";
import { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { fonte, useTema } from "@/tema";

import { Icone } from "./Icone";

let mostrar: ((texto: string) => void) | null = null;

/** Chame de qualquer tela: "Pôs na lista: Feijão carioca". */
export function confirmar(texto: string): void {
  mostrar?.(texto);
  void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
}

/** Fica no _layout raiz, por cima de todas as telas. */
export function Confirmacao() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const [texto, setTexto] = useState<string | null>(null);
  const [entrada] = useState(() => new Animated.Value(0));
  const reduzir = useRef(false);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then((v) => {
      reduzir.current = v;
    });
    let relogio: ReturnType<typeof setTimeout> | undefined;
    mostrar = (t) => {
      setTexto(t);
      entrada.setValue(reduzir.current ? 1 : 0);
      if (!reduzir.current) Animated.timing(entrada, { toValue: 1, duration: 250, useNativeDriver: true }).start();
      if (relogio) clearTimeout(relogio);
      relogio = setTimeout(() => setTexto(null), 1600);
    };
    return () => {
      mostrar = null;
      if (relogio) clearTimeout(relogio);
    };
  }, [entrada]);

  if (!texto) return null;
  const escala = entrada.interpolate({ inputRange: [0, 1], outputRange: [0.92, 1] });
  return (
    <View pointerEvents="none" style={[estilos.camada, { bottom: margem.bottom + 88 }]}>
      <Animated.View
        accessibilityLiveRegion="polite"
        style={[estilos.aviso, { backgroundColor: cor.fundoProfundo, opacity: entrada, transform: [{ scale: escala }] }]}
      >
        <View style={[estilos.ok, { backgroundColor: cor.estadoEconomia }]}>
          <Icone nome="ok" cor={cor.textoInverso} tamanho={16} />
        </View>
        <Text numberOfLines={2} style={[fonte("corpoForte"), { color: cor.textoInverso, flexShrink: 1 }]}>
          {texto}
        </Text>
      </Animated.View>
    </View>
  );
}

const estilos = StyleSheet.create({
  camada: { position: "absolute", left: 20, right: 20, alignItems: "center" },
  aviso: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12, paddingHorizontal: 16, borderRadius: 16, maxWidth: "100%" },
  ok: { width: 24, height: 24, borderRadius: 12, alignItems: "center", justifyContent: "center" },
});
