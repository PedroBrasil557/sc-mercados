/**
 * 20 "Não perca a sua lista" (R16): um código de recuperação para usar a mesma conta num celular novo.
 * Sem e-mail, sem telefone, sem CPF. (Entrar com e-mail fica para quando houver um provedor de envio.)
 */
import * as Clipboard from "expo-clipboard";
import { useState } from "react";
import { Share, StyleSheet, Text, View } from "react-native";

import { api } from "@/api/cliente";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Icone } from "./Icone";
import { PainelInferior } from "./PainelInferior";

export function PainelRecuperacao({ visivel, aoFechar }: { visivel: boolean; aoFechar: () => void }) {
  const { cor } = useTema();
  const [codigo, setCodigo] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function gerar() {
    setOcupado(true);
    setErro(null);
    try {
      setCodigo((await api.gerarRecuperacao()).codigo);
    } catch {
      setErro("Sem internet: o código precisa de conexão.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <PainelInferior
      visivel={visivel}
      titulo="Não perca a sua lista"
      aoFechar={aoFechar}
      rodape={
        <View style={{ gap: 8 }}>
          {codigo ? (
            <Botao
              rotulo="Guardar no WhatsApp ou nas notas"
              largo
              aoTocar={() => void Share.share({ message: `Código de recuperação do SC Mercados: ${codigo}\nUse em "Recuperar minha lista" num celular novo.` })}
            />
          ) : (
            <Botao rotulo="Criar meu código de recuperação" largo ocupado={ocupado} aoTocar={() => void gerar()} />
          )}
          <Botao rotulo="Agora não" tipo="contorno" largo aoTocar={aoFechar} />
        </View>
      }
    >
      <View style={[estilos.icone, { backgroundColor: cor.estadoEconomiaSuave }]}>
        <Icone nome="familia" cor={cor.estadoEconomia} tamanho={32} />
      </View>
      <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>
        Se você trocar de celular, este código traz a mesma lista, com a mesma casa. Guarde num lugar seu.
      </Text>
      {codigo ? (
        <View style={[estilos.codigo, { backgroundColor: cor.fundoAfundado }]}>
          <Text selectable style={[fonte("precoMedio"), { color: cor.textoPrincipal, letterSpacing: 2, flex: 1, textAlign: "center" }]}>
            {codigo}
          </Text>
          <Botao rotulo="Copiar" tipo="contorno" aoTocar={() => void Clipboard.setStringAsync(codigo)} />
        </View>
      ) : null}
      {erro ? <Text style={[fonte("corpoMenor"), { color: cor.estadoAlerta, textAlign: "center" }]}>{erro}</Text> : null}
      <Text style={[fonte("legenda"), { color: cor.textoSuave, textAlign: "center" }]}>Pedimos só o necessário. Nada de CPF, e-mail ou telefone.</Text>
    </PainelInferior>
  );
}

const estilos = StyleSheet.create({
  icone: { alignSelf: "center", width: 56, height: 56, borderRadius: 28, alignItems: "center", justifyContent: "center" },
  codigo: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 14 },
});
