import { Redirect } from "expo-router";
import { TabList, TabSlot, TabTrigger, Tabs } from "expo-router/ui";
import { StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { BotaoDeAba } from "@/componentes/BotaoDeAba";
import { useLista } from "@/lista/sincronia";
import { useTema } from "@/tema";

export default function AbasLayout() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao } = useLista();
  // Sem casa ainda: a primeira abertura começa nas boas-vindas.
  if (!sessao) return <Redirect href="/boas-vindas" />;
  return (
    <Tabs>
      <TabSlot />
      <View pointerEvents="none" style={[estilos.status, { height: margem.top, backgroundColor: cor.fundoTela }]} />
      <TabList
        accessibilityRole="tablist"
        style={[estilos.barra, { backgroundColor: cor.fundoSuperficie, borderTopColor: cor.bordaPadrao, paddingBottom: margem.bottom }]}
      >
        <TabTrigger name="inicio" href="/" asChild>
          <BotaoDeAba icone="inicio" rotulo="Início" />
        </TabTrigger>
        <TabTrigger name="lista" href="/lista" asChild>
          <BotaoDeAba icone="lista" rotulo="Lista" />
        </TabTrigger>
        <TabTrigger name="comparar" href="/comparar" asChild>
          <BotaoDeAba icone="comparar" rotulo="Comparar" />
        </TabTrigger>
        <TabTrigger name="ofertas" href="/ofertas" asChild>
          <BotaoDeAba icone="oferta" rotulo="Ofertas" />
        </TabTrigger>
        <TabTrigger name="perfil" href="/perfil" asChild>
          <BotaoDeAba icone="perfil" rotulo="Perfil" />
        </TabTrigger>
      </TabList>
    </Tabs>
  );
}

const estilos = StyleSheet.create({
  status: { position: "absolute", top: 0, left: 0, right: 0 },
  barra: { flexDirection: "row", borderTopWidth: StyleSheet.hairlineWidth },
});
