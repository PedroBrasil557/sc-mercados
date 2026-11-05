// Cada peso vem da sua subpasta: importar da raiz do pacote embutiria todos os pesos (~3 MB a mais).
import { BricolageGrotesque_600SemiBold } from "@expo-google-fonts/bricolage-grotesque/600SemiBold";
import { BricolageGrotesque_700Bold } from "@expo-google-fonts/bricolage-grotesque/700Bold";
import { BricolageGrotesque_800ExtraBold } from "@expo-google-fonts/bricolage-grotesque/800ExtraBold";
import { Figtree_400Regular } from "@expo-google-fonts/figtree/400Regular";
import { Figtree_500Medium } from "@expo-google-fonts/figtree/500Medium";
import { Figtree_600SemiBold } from "@expo-google-fonts/figtree/600SemiBold";
import { Figtree_700Bold } from "@expo-google-fonts/figtree/700Bold";
import { IBMPlexMono_500Medium } from "@expo-google-fonts/ibm-plex-mono/500Medium";
import { useFonts } from "expo-font";
import { type ErrorBoundaryProps, Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { useEffect } from "react";
import { Pressable, Text, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { Confirmacao } from "@/componentes/Confirmacao";
import { instalarRelatorioDeErros, relatarErro } from "@/erros";
import { useSincroniaAutomatica } from "@/lista/sincronia";
import { useTema } from "@/tema";

SplashScreen.preventAutoHideAsync();
instalarRelatorioDeErros();

/** Erro em qualquer tela: avisa a API (aba "Erros do app" do painel) e mostra uma saída em vez de tela branca. */
export function ErrorBoundary({ error, retry }: ErrorBoundaryProps) {
  const { cor } = useTema();
  useEffect(() => {
    relatarErro(error, "tela", true);
  }, [error]);
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 16, padding: 32, backgroundColor: cor.fundoTela }}>
      <Text style={{ fontSize: 20, fontWeight: "700", color: cor.textoPrincipal, textAlign: "center" }}>Algo deu errado nesta tela</Text>
      <Text style={{ fontSize: 15, color: cor.textoSuave, textAlign: "center" }}>
        Já avisamos a equipe. Sua lista está guardada no celular e não se perdeu.
      </Text>
      <Pressable
        accessibilityRole="button"
        onPress={retry}
        style={{ paddingVertical: 14, paddingHorizontal: 28, borderRadius: 12, backgroundColor: cor.estadoEconomia }}
      >
        <Text style={{ fontSize: 16, fontWeight: "700", color: cor.textoInverso }}>Tentar de novo</Text>
      </Pressable>
    </View>
  );
}

export default function RaizLayout() {
  const { cor, modo } = useTema();
  useSincroniaAutomatica();
  const [carregou, erro] = useFonts({
    BricolageGrotesque_600SemiBold,
    BricolageGrotesque_700Bold,
    BricolageGrotesque_800ExtraBold,
    Figtree_400Regular,
    Figtree_500Medium,
    Figtree_600SemiBold,
    Figtree_700Bold,
    IBMPlexMono_500Medium,
  });

  useEffect(() => {
    SystemUI.setBackgroundColorAsync(cor.fundoTela);
  }, [cor.fundoTela]);

  useEffect(() => {
    if (carregou || erro) SplashScreen.hideAsync();
  }, [carregou, erro]);

  // Sem as fontes, o texto apareceria numa fonte do sistema e depois "pularia": melhor segurar a abertura.
  if (!carregou && !erro) return null;

  return (
    <SafeAreaProvider>
      <StatusBar style={modo === "escuro" ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: cor.fundoTela } }}>
        <Stack.Screen name="(abas)" />
        <Stack.Screen name="boas-vindas" />
        <Stack.Screen name="adicionar" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="dados" />
        <Stack.Screen name="produto/[id]" />
        <Stack.Screen name="no-mercado" />
        <Stack.Screen name="ler-cupom" options={{ animation: "slide_from_bottom" }} />
        <Stack.Screen name="cupom-lido" options={{ gestureEnabled: false }} />
        <Stack.Screen name="seu-mercado" options={{ animation: "slide_from_bottom" }} />
      </Stack>
      <Confirmacao />
    </SafeAreaProvider>
  );
}
