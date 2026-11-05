/**
 * Monitoramento de erros próprio (sem serviço de terceiros): o erro vai para a API do SC Mercados e aparece no
 * painel, na aba "Erros do app". Nada que identifique a pessoa: sem token, sem lista, sem casa.
 */
import Constants from "expo-constants";
import { Platform } from "react-native";

import { API } from "@/api/cliente";

const enviados = new Set<string>(); // o mesmo erro uma vez por sessão: um laço de erro não vira enxurrada

export function relatarErro(erro: unknown, onde = "global", fatal = false): void {
  const e = erro instanceof Error ? erro : new Error(String(erro));
  const mensagem = (e.message || e.name || "erro sem mensagem").slice(0, 500);
  const chave = `${onde}|${mensagem}`;
  if (enviados.has(chave)) return;
  enviados.add(chave);
  fetch(`${API}/v1/erros`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mensagem,
      pilha: e.stack?.slice(0, 4000) ?? null,
      onde: onde.slice(0, 120),
      versao: Constants.expoConfig?.version ?? "?",
      plataforma: `${Platform.OS} ${Platform.Version}`.slice(0, 40),
      ambiente: __DEV__ ? "desenvolvimento" : "publicado",
      fatal,
    }),
  }).catch(() => {
    // sem internet: o erro se perde, e tudo bem (não guardamos nada no aparelho)
  });
}

type ErrorUtilsGlobal = {
  getGlobalHandler: () => (erro: Error, fatal?: boolean) => void;
  setGlobalHandler: (f: (erro: Error, fatal?: boolean) => void) => void;
};

/** Erro que nenhuma tela tratou (inclusive fora do React): manda e segue o tratamento normal do React Native. */
export function instalarRelatorioDeErros(): void {
  const utilidades = (globalThis as { ErrorUtils?: ErrorUtilsGlobal }).ErrorUtils;
  if (!utilidades) return;
  const anterior = utilidades.getGlobalHandler();
  utilidades.setGlobalHandler((erro, fatal) => {
    relatarErro(erro, "global", !!fatal);
    anterior(erro, fatal);
  });
}
