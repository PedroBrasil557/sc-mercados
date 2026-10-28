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
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import * as SystemUI from "expo-system-ui";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { useTema } from "@/tema";

SplashScreen.preventAutoHideAsync();

export default function RaizLayout() {
  const { cor, modo } = useTema();
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
      </Stack>
    </SafeAreaProvider>
  );
}
