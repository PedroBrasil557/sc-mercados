/** Liga/desliga o aviso de quinta, com a explicação antes do pedido de permissão do sistema (tela 28). */
import { useState, useSyncExternalStore } from "react";
import { Alert, Linking, StyleSheet, Switch, Text, View } from "react-native";

import { assinarAviso, avisoLigado, desligarAvisoDeQuinta, ligarAvisoDeQuinta, permissaoJaDada } from "@/avisos";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Icone } from "./Icone";
import { PainelInferior } from "./PainelInferior";

export function useAvisoDeQuinta() {
  const ligado = useSyncExternalStore(assinarAviso, avisoLigado);
  const [explicando, setExplicando] = useState(false);

  async function ligar() {
    setExplicando(false);
    const ok = await ligarAvisoDeQuinta();
    if (!ok) {
      Alert.alert("Avisos desligados no celular", "Para receber o aviso de quinta, permita as notificações do SC Mercados nas configurações.", [
        { text: "Agora não", style: "cancel" },
        { text: "Abrir configurações", onPress: () => void Linking.openSettings() },
      ]);
    }
  }

  async function alternar(novo: boolean) {
    if (!novo) {
      return desligarAvisoDeQuinta();
    }
    if (await permissaoJaDada()) return ligar();
    setExplicando(true);
  }

  return { ligado, alternar, explicando, ligar, fecharExplicacao: () => setExplicando(false) };
}

/** 28 Permissão dos avisos: por que o app quer avisar, antes do diálogo do sistema. */
export function ExplicacaoDosAvisos({ visivel, aoPermitir, aoFechar }: { visivel: boolean; aoPermitir: () => void; aoFechar: () => void }) {
  const { cor } = useTema();
  return (
    <PainelInferior
      visivel={visivel}
      titulo="Toda quinta, suas ofertas"
      aoFechar={aoFechar}
      rodape={
        <View style={{ gap: 8 }}>
          <Botao rotulo="Permitir avisos" largo aoTocar={aoPermitir} />
          <Botao rotulo="Agora não" tipo="contorno" largo aoTocar={aoFechar} />
        </View>
      }
    >
      <View style={[estilos.icone, { backgroundColor: cor.marcaEtiqueta }]}>
        <Icone nome="aviso" cor={cor.marcaSobreEtiqueta} tamanho={32} />
      </View>
      <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
        Um aviso por semana, na quinta à tarde, quando os mercados atualizam os encartes. Nada de propaganda: só as ofertas reais dos
        itens da sua lista. Dá para desligar quando quiser.
      </Text>
    </PainelInferior>
  );
}

export function ChaveDoAviso({ ligado, aoMudar, inverso = false, semRotulo = false }: { ligado: boolean; aoMudar: (v: boolean) => void; inverso?: boolean; semRotulo?: boolean }) {
  const { cor } = useTema();
  return (
    <View style={estilos.chave}>
      {semRotulo ? null : <Text style={[fonte("corpoForte"), { color: inverso ? cor.textoInverso : cor.textoPrincipal, flex: 1 }]}>{ligado ? "Ligado" : "Desligado"}</Text>}
      <Switch
        accessibilityLabel="Aviso de ofertas às quintas"
        value={ligado}
        onValueChange={aoMudar}
        trackColor={{ true: cor.marcaEtiqueta, false: cor.bordaForte }}
        thumbColor={ligado ? cor.fundoProfundo : cor.fundoSuperficie}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  icone: { alignSelf: "center", width: 64, height: 64, borderRadius: 32, alignItems: "center", justifyContent: "center" },
  chave: { flexDirection: "row", alignItems: "center", gap: 8 },
});
