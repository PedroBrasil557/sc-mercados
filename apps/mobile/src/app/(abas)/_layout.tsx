import { TabList, TabSlot, TabTrigger, Tabs } from "expo-router/ui";
import { StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { BotaoDeAba } from "@/componentes/BotaoDeAba";
import { useTema } from "@/tema";

export default function AbasLayout() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  return (
    <Tabs>
      <TabSlot />
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
          <BotaoDeAba icone="ofertas" rotulo="Ofertas" />
        </TabTrigger>
        <TabTrigger name="perfil" href="/perfil" asChild>
          <BotaoDeAba icone="perfil" rotulo="Perfil" />
        </TabTrigger>
      </TabList>
    </Tabs>
  );
}

const estilos = StyleSheet.create({
  barra: { flexDirection: "row", borderTopWidth: StyleSheet.hairlineWidth },
});
