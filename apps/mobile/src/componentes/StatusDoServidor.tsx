import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "@/api/cliente";
import { fonte, useTema } from "@/tema";

type Estado = { tipo: "verificando" } | { tipo: "ok"; bairros: number; ms: number } | { tipo: "erro"; mensagem: string };

/** Diagnóstico para o teste no celular: o aparelho alcança a API e o banco responde? */
export function StatusDoServidor() {
  const { cor, medida } = useTema();
  const [estado, setEstado] = useState<Estado>({ tipo: "verificando" });

  useEffect(() => {
    const inicio = Date.now();
    api
      .bairros()
      .then((b) => setEstado({ tipo: "ok", bairros: b.length, ms: Date.now() - inicio }))
      .catch((e: unknown) => setEstado({ tipo: "erro", mensagem: e instanceof Error ? e.message : String(e) }));
  }, []);

  const [ponto, texto] =
    estado.tipo === "verificando"
      ? [cor.bordaForte, "Verificando o servidor…"]
      : estado.tipo === "ok"
        ? [cor.estadoEconomia, `Servidor conectado · ${estado.bairros} bairros · ${estado.ms} ms`]
        : [cor.estadoAlerta, `Sem conexão com o servidor: ${estado.mensagem}`];

  return (
    <View
      accessibilityRole="summary"
      style={[estilos.linha, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderRadius: medida.raioMedio }]}
    >
      <View style={[estilos.ponto, { backgroundColor: ponto }]} />
      <Text style={[fonte("corpoMenor"), estilos.texto, { color: cor.textoPrincipal }]}>{texto}</Text>
    </View>
  );
}

const estilos = StyleSheet.create({
  linha: { flexDirection: "row", alignItems: "center", gap: 10, padding: 14, borderWidth: StyleSheet.hairlineWidth },
  ponto: { width: 10, height: 10, borderRadius: 5 },
  texto: { flex: 1 },
});
