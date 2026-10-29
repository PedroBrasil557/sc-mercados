/** 09 Ler cupom fiscal, 26 Permissão da câmera e 21 Cupom não lido. */
import { CameraView, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";
import { useRef, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { WebView, type WebViewMessageEvent } from "react-native-webview";

import { api, ErroDaApi } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Campo } from "@/componentes/Campo";
import { Icone } from "@/componentes/Icone";
import { converter, enderecoDaConsulta, extrairChave, SCRIPT_DE_LEITURA } from "@/cupom/nfce";
import { fonte, useTema } from "@/tema";

type Etapa = { tipo: "camera" } | { tipo: "digitar" } | { tipo: "consulta"; url: string; chave: string } | { tipo: "enviando" } | { tipo: "erro"; motivo: string; url?: string; chave?: string };

export default function LerCupom() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const [permissao, pedirPermissao] = useCameraPermissions();
  const [etapa, setEtapa] = useState<Etapa>({ tipo: "camera" });
  const [chaveDigitada, setChaveDigitada] = useState("");
  const lido = useRef(false);

  function aoLerQr(texto: string) {
    if (lido.current) return;
    const chave = extrairChave(texto);
    if (!chave) return; // outro QR qualquer: continua procurando
    lido.current = true;
    setEtapa({ tipo: "consulta", url: enderecoDaConsulta(texto, chave), chave });
  }

  async function aoReceber(evento: WebViewMessageEvent, url: string, chave: string) {
    const cupom = converter(evento.nativeEvent.data);
    if (!cupom) return setEtapa({ tipo: "erro", motivo: "A página da Sefaz não mostrou os itens.", url, chave });
    setEtapa({ tipo: "enviando" });
    try {
      const resultado = await api.lerCupom({ chave, ...cupom });
      router.replace({ pathname: "/cupom-lido", params: { resultado: JSON.stringify(resultado), data: cupom.emitido_em } });
    } catch (e) {
      const motivo = e instanceof ErroDaApi ? (e.status === 409 ? "Este cupom já foi lido antes." : e.message) : "Sem internet para enviar o cupom.";
      setEtapa({ tipo: "erro", motivo, url, chave });
    }
  }

  const fechar = (
    <Pressable accessibilityRole="button" accessibilityLabel="Fechar" hitSlop={8} onPress={() => router.back()} style={estilos.fechar}>
      <Icone nome="fechar" cor={etapa.tipo === "camera" ? cor.textoInverso : cor.textoPrincipal} />
    </Pressable>
  );

  // 26 Permissão da câmera: explica antes do pedido do sistema.
  if (etapa.tipo === "camera" && !permissao?.granted) {
    return (
      <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8, paddingBottom: margem.bottom + 16 }]}>
        {fechar}
        <View style={estilos.centro}>
          <View style={[estilos.circulo, { backgroundColor: cor.estadoEconomiaSuave }]}>
            <Icone nome="camera" cor={cor.estadoEconomia} tamanho={40} />
          </View>
          <Text style={[fonte("tituloTela"), { color: cor.textoPrincipal, textAlign: "center" }]}>A câmera lê o QR do cupom</Text>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>
            Só o QR, só enquanto esta tela está aberta. Nenhuma foto é guardada ou enviada.
          </Text>
        </View>
        <View style={{ gap: 8, paddingHorizontal: 24 }}>
          {permissao && !permissao.canAskAgain ? (
            <Botao rotulo="Abrir configurações" largo aoTocar={() => void Linking.openSettings()} />
          ) : (
            <Botao rotulo="Permitir a câmera" largo aoTocar={() => void pedirPermissao()} />
          )}
          <Botao rotulo="Digitar a chave de acesso" tipo="contorno" largo aoTocar={() => setEtapa({ tipo: "digitar" })} />
        </View>
      </View>
    );
  }

  if (etapa.tipo === "camera") {
    return (
      <View style={[estilos.tela, { backgroundColor: cor.fundoProfundo }]}>
        <CameraView style={StyleSheet.absoluteFill} facing="back" barcodeScannerSettings={{ barcodeTypes: ["qr"] }} onBarcodeScanned={(r) => aoLerQr(r.data)} />
        <View style={[estilos.cabecalhoEscuro, { paddingTop: margem.top + 8 }]}>
          {fechar}
          <Text style={[fonte("tituloSecao"), { color: cor.textoInverso }]}>Ler cupom fiscal</Text>
        </View>
        <View style={estilos.mira} pointerEvents="none">
          <View style={[estilos.moldura, { borderColor: cor.marcaEtiqueta }]} />
        </View>
        <View style={[estilos.rodapeEscuro, { paddingBottom: margem.bottom + 24, backgroundColor: cor.fundoProfundo }]}>
          <Text style={[fonte("tituloSecao"), { color: cor.textoInverso, textAlign: "center" }]}>Aponte para o QR no fim do cupom</Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoInverso, textAlign: "center" }]}>A leitura é automática e acontece no seu celular.</Text>
          <View style={[estilos.selo, { borderColor: cor.sobreposicaoDivisor }]}>
            <Icone nome="info" cor={cor.textoInverso} tamanho={16} />
            <Text style={[fonte("legenda"), { color: cor.textoInverso }]}>O CPF fica no cupom: o app não lê nem envia</Text>
          </View>
          <Pressable accessibilityRole="button" onPress={() => setEtapa({ tipo: "digitar" })} style={estilos.link}>
            <Text style={[fonte("corpoForte"), { color: cor.marcaEtiqueta, textDecorationLine: "underline" }]}>Digitar a chave de acesso</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if (etapa.tipo === "digitar") {
    const chave = extrairChave(chaveDigitada);
    return (
      <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8 }]}>
        {fechar}
        <View style={{ padding: 24, gap: 16 }}>
          <Text style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>Chave de acesso</Text>
          <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>São os 44 números perto do QR, no fim do cupom.</Text>
          <Campo rotulo="Chave de acesso" keyboardType="number-pad" value={chaveDigitada} onChangeText={setChaveDigitada} maxLength={60} placeholder="0000 0000 0000 …" />
          <Botao rotulo="Consultar" largo desativado={!chave} aoTocar={() => chave && setEtapa({ tipo: "consulta", url: enderecoDaConsulta(chave, chave), chave })} />
        </View>
      </View>
    );
  }

  if (etapa.tipo === "consulta") {
    return (
      <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8 }]}>
        <View style={estilos.cabecalho}>
          {fechar}
          <View style={{ flex: 1 }}>
            <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>Lendo o cupom na Sefaz…</Text>
            <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Se aparecer &quot;Não sou um robô&quot;, é só tocar.</Text>
          </View>
        </View>
        <WebView
          source={{ uri: etapa.url }}
          injectedJavaScript={SCRIPT_DE_LEITURA}
          onMessage={(e) => void aoReceber(e, etapa.url, etapa.chave)}
          onError={() => setEtapa({ tipo: "erro", motivo: "Não deu para abrir a consulta da Sefaz.", url: etapa.url, chave: etapa.chave })}
          incognito
          setSupportMultipleWindows={false}
          style={{ flex: 1 }}
        />
      </View>
    );
  }

  if (etapa.tipo === "enviando") {
    return (
      <View style={[estilos.tela, estilos.centro, { backgroundColor: cor.fundoTela }]}>
        <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>Conferindo os preços…</Text>
      </View>
    );
  }

  // 21 Cupom não lido
  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8, paddingBottom: margem.bottom + 16 }]}>
      {fechar}
      <View style={[estilos.centro, { paddingHorizontal: 24 }]}>
        <View style={[estilos.circulo, { backgroundColor: cor.estadoAlertaSuave }]}>
          <Icone nome="cupom" cor={cor.estadoAlerta} tamanho={40} />
        </View>
        <Text style={[fonte("tituloTela"), { color: cor.textoPrincipal, textAlign: "center" }]}>Não conseguimos ler este cupom</Text>
        <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave, textAlign: "center" }]}>{etapa.motivo}</Text>
      </View>
      <View style={{ gap: 8, paddingHorizontal: 24 }}>
        <Botao
          rotulo="Tentar de novo"
          tipo="etiqueta"
          largo
          aoTocar={() => {
            lido.current = false;
            setEtapa({ tipo: "camera" });
          }}
        />
        {etapa.url && etapa.chave ? (
          <Botao rotulo="Abrir a consulta da Sefaz no app" tipo="contorno" largo aoTocar={() => setEtapa({ tipo: "consulta", url: etapa.url!, chave: etapa.chave! })} />
        ) : null}
        <Botao rotulo="Digitar a chave de acesso" tipo="contorno" largo aoTocar={() => setEtapa({ tipo: "digitar" })} />
        <View style={[estilos.dica, { backgroundColor: cor.fundoAfundado }]}>
          <Icone nome="info" cor={cor.textoPrincipal} tamanho={20} />
          <Text style={[fonte("legenda"), { color: cor.textoPrincipal, flex: 1 }]}>
            Na consulta da Sefaz, se aparecer &quot;Não sou um robô&quot;, é só tocar. O app lê os itens depois.
          </Text>
        </View>
      </View>
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  fechar: { width: 48, height: 48, alignItems: "center", justifyContent: "center", marginLeft: 8 },
  centro: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, paddingHorizontal: 24 },
  circulo: { width: 96, height: 96, borderRadius: 48, alignItems: "center", justifyContent: "center", marginBottom: 8 },
  cabecalhoEscuro: { flexDirection: "row", alignItems: "center", gap: 4 },
  cabecalho: { flexDirection: "row", alignItems: "center", gap: 4, paddingRight: 20, paddingBottom: 8 },
  mira: { flex: 1, alignItems: "center", justifyContent: "center" },
  moldura: { width: 240, height: 240, borderWidth: 4, borderRadius: 24 },
  rodapeEscuro: { paddingTop: 24, paddingHorizontal: 24, gap: 10, alignItems: "center", borderTopLeftRadius: 28, borderTopRightRadius: 28 },
  selo: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  link: { minHeight: 44, justifyContent: "center" },
  dica: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12, marginTop: 8 },
});
