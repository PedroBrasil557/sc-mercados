/**
 * 13 Aviso de quinta: um lembrete local por semana (quinta, 15h), quando os encartes entram nos sites.
 * Notificação local: funciona sem servidor de push e também no Expo Go.
 * A permissão (Android 13+) só é pedida quando a pessoa liga o aviso (exigência da Google Play).
 */
import * as Notifications from "expo-notifications";
import { AndroidImportance } from "expo-notifications";
import { Platform } from "react-native";

import * as armazem from "@/lista/armazem";

const CHAVE = "aviso_quinta";
const CANAL = "ofertas";
const QUINTA = 5; // 1 = domingo

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false }),
});

export const avisoLigado = (): boolean => !!armazem.lerGuardado<string>(CHAVE);

// Ofertas e Perfil mostram a mesma chave: as duas telas escutam a mesma mudança.
const ouvintes = new Set<() => void>();
export function assinarAviso(f: () => void): () => void {
  ouvintes.add(f);
  return () => ouvintes.delete(f);
}
const avisar = () => ouvintes.forEach((f) => f());

export async function permissaoJaDada(): Promise<boolean> {
  return (await Notifications.getPermissionsAsync()).granted;
}

/** Liga o aviso. Devolve false se a pessoa negou a permissão no sistema. */
export async function ligarAvisoDeQuinta(): Promise<boolean> {
  const atual = await Notifications.getPermissionsAsync();
  const permissao = atual.granted ? atual : await Notifications.requestPermissionsAsync();
  if (!permissao.granted) return false;
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(CANAL, { name: "Ofertas de quinta-feira", importance: AndroidImportance.DEFAULT });
  }
  await desligarAvisoDeQuinta();
  const id = await Notifications.scheduleNotificationAsync({
    content: { title: "Ofertas da semana", body: "Os mercados de Blumenau atualizaram os preços. Veja as ofertas reais nos itens da sua lista." },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.WEEKLY, weekday: QUINTA, hour: 15, minute: 0, channelId: CANAL },
  });
  armazem.guardar(CHAVE, id);
  avisar();
  return true;
}

export async function desligarAvisoDeQuinta(): Promise<void> {
  const id = armazem.lerGuardado<string>(CHAVE);
  if (id) await Notifications.cancelScheduledNotificationAsync(id).catch(() => undefined);
  armazem.guardar(CHAVE, null);
  avisar();
}
