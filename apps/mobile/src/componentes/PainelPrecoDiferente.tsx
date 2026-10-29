/** 19 Preço diferente na etiqueta (R11): o preço só muda no app depois de confirmado. */
import { useState } from "react";
import { Alert, StyleSheet, Text, TextInput, View } from "react-native";

import { api } from "@/api/cliente";
import { reais } from "@/formatar";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Icone } from "./Icone";
import { Miniatura } from "./Miniatura";
import { PainelInferior } from "./PainelInferior";

type Props = {
  visivel: boolean;
  aoFechar: () => void;
  produto: { id: string; nome: string; categoria: string | null; tamanho: string | null; marca?: string | null };
  loja: { id: string; nome: string; preco_centavos: number } | null;
};

export function PainelPrecoDiferente({ visivel, aoFechar, produto, loja }: Props) {
  const { cor } = useTema();
  const [digitos, setDigitos] = useState("");
  const [enviando, setEnviando] = useState(false);
  const centavos = Number(digitos || "0");

  async function enviar() {
    if (!loja || !centavos) return;
    setEnviando(true);
    try {
      await api.reportarPreco(produto.id, loja.id, centavos);
      setDigitos("");
      aoFechar();
      Alert.alert("Obrigado!", "O preço vai ser conferido. Quando for confirmado, muda no app para todo mundo.");
    } catch {
      Alert.alert("Sem internet", "Não deu para enviar agora. Tente de novo em instantes.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <PainelInferior
      visivel={visivel}
      titulo="Preço diferente na etiqueta?"
      aoFechar={aoFechar}
      rodape={<Botao rotulo="Enviar" largo ocupado={enviando} desativado={!centavos || !loja} aoTocar={() => void enviar()} />}
    >
      <View style={estilos.produto}>
        <Miniatura categoria={produto.categoria} tamanho={produto.tamanho} nome={produto.nome} />
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{[produto.nome, produto.marca].filter(Boolean).join(" · ")}</Text>
          {loja ? (
            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
              No app: {reais(loja.preco_centavos)} · {loja.nome}
            </Text>
          ) : null}
        </View>
      </View>
      <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Preço na etiqueta</Text>
      <View style={[estilos.campo, { borderColor: cor.estadoEconomia }]}>
        <TextInput
          autoFocus
          accessibilityLabel="Preço na etiqueta, em reais"
          keyboardType="number-pad"
          value={centavos ? reais(centavos) : ""}
          placeholder={reais(0)}
          placeholderTextColor={cor.textoSuave}
          // Digita como na maquininha: os números entram pelos centavos (4, 9, 9 → R$ 4,99).
          onChangeText={(t) => setDigitos(t.replace(/\D/g, "").replace(/^0+/, "").slice(0, 7))}
          style={[fonte("precoGrande"), { color: cor.textoPrincipal, flex: 1, paddingVertical: 0 }]}
        />
      </View>
      <View style={[estilos.info, { backgroundColor: cor.fundoAfundado }]}>
        <Icone nome="info" cor={cor.textoPrincipal} tamanho={20} />
        <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>
          O preço só muda no app depois de confirmado por outra pessoa ou por um cupom.
        </Text>
      </View>
    </PainelInferior>
  );
}

const estilos = StyleSheet.create({
  produto: { flexDirection: "row", alignItems: "center", gap: 12 },
  campo: { height: 64, borderRadius: 16, borderWidth: 2, paddingHorizontal: 16, justifyContent: "center", flexDirection: "row", alignItems: "center" },
  info: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12 },
});
