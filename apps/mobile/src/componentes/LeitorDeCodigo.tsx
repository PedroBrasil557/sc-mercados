/** Leitor de código de barras (botão escuro do campo de busca): aponta para o produto e ele entra na lista. */
import { CameraView, useCameraPermissions } from "expo-camera";
import { useRef, useState } from "react";
import { Linking, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, ErroDaApi, type Produto } from "@/api/cliente";
import { fonte, useTema } from "@/tema";

import { Botao } from "./Botao";
import { Icone } from "./Icone";

export function LeitorDeCodigo({ visivel, aoFechar, aoAchar }: { visivel: boolean; aoFechar: () => void; aoAchar: (p: Produto) => void }) {
  return (
    <Modal visible={visivel} animationType="slide" onRequestClose={aoFechar} statusBarTranslucent>
      {visivel ? <Leitor aoFechar={aoFechar} aoAchar={aoAchar} /> : null}
    </Modal>
  );
}

function Leitor({ aoFechar, aoAchar }: { aoFechar: () => void; aoAchar: (p: Produto) => void }) {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const [permissao, pedir] = useCameraPermissions();
  const [aviso, setAviso] = useState<string | null>(null);
  const ocupado = useRef(false);
  const ultimo = useRef("");

  async function aoLer(codigo: string) {
    if (ocupado.current || codigo === ultimo.current) return;
    ocupado.current = true;
    ultimo.current = codigo;
    try {
      aoAchar(await api.produtoPorEan(codigo));
      aoFechar();
    } catch (e) {
      setAviso(e instanceof ErroDaApi && e.status === 404 ? "Este produto ainda não está no catálogo. Busque pelo nome." : "Sem internet para buscar o código.");
    } finally {
      ocupado.current = false;
    }
  }

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoProfundo }]}>
      {permissao?.granted ? (
        <CameraView
          style={StyleSheet.absoluteFill}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e"] }}
          onBarcodeScanned={(r) => void aoLer(r.data)}
        />
      ) : null}
      <View style={[estilos.topo, { paddingTop: margem.top + 8 }]}>
        <Pressable accessibilityRole="button" accessibilityLabel="Fechar" hitSlop={8} onPress={aoFechar} style={estilos.fechar}>
          <Icone nome="fechar" cor={cor.textoInverso} />
        </Pressable>
        <Text style={[fonte("tituloSecao"), { color: cor.textoInverso }]}>Ler código de barras</Text>
      </View>
      <View style={estilos.centro} pointerEvents="box-none">
        {permissao?.granted ? (
          <View style={[estilos.moldura, { borderColor: cor.marcaEtiqueta }]} pointerEvents="none" />
        ) : (
          <View style={{ gap: 12, paddingHorizontal: 32, alignItems: "center" }}>
            <Icone nome="camera" cor={cor.textoInverso} tamanho={40} />
            <Text style={[fonte("corpoPadrao"), { color: cor.textoInverso, textAlign: "center" }]}>
              A câmera lê só o código de barras, enquanto esta tela está aberta. Nenhuma foto é guardada.
            </Text>
            {permissao && !permissao.canAskAgain ? (
              <Botao rotulo="Abrir configurações" tipo="etiqueta" aoTocar={() => void Linking.openSettings()} />
            ) : (
              <Botao rotulo="Permitir a câmera" tipo="etiqueta" aoTocar={() => void pedir()} />
            )}
          </View>
        )}
      </View>
      <View style={[estilos.rodape, { paddingBottom: margem.bottom + 24 }]}>
        <Text accessibilityLiveRegion="polite" style={[fonte("corpoMenor"), { color: cor.textoInverso, textAlign: "center" }]}>
          {aviso ?? "Aponte para o código de barras da embalagem."}
        </Text>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  topo: { flexDirection: "row", alignItems: "center", gap: 4 },
  fechar: { width: 48, height: 48, alignItems: "center", justifyContent: "center", marginLeft: 8 },
  centro: { flex: 1, alignItems: "center", justifyContent: "center" },
  moldura: { width: 280, height: 160, borderWidth: 4, borderRadius: 20 },
  rodape: { paddingHorizontal: 24, paddingTop: 16 },
});
