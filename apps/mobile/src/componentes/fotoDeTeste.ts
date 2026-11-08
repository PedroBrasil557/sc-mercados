import { useEffect, useState } from "react";

import { api } from "@/api/cliente";
import * as armazem from "@/lista/armazem";
import { MODO_TESTE } from "@/modoTeste";

// Foto do produto tirada do site de uma rede (Giassi, Cooper, Angeloni...). É da rede ou do fabricante: só aparece no
// modo de teste (Expo Go ou APK de teste, ver modoTeste.ts), para ver como o app fica com fotos. A versão publicada mostra a miniatura até
// haver autorização das redes.
// Endereços já conhecidos ficam guardados no celular: ao abrir o app, as miniaturas não esperam o servidor e a
// foto vem do cache do expo-image.
const GUARDADO = "fotos_teste";
const fotos = new Map<string, string | null>(Object.entries(lerFotosGuardadas()));
let gravacao: ReturnType<typeof setTimeout> | null = null;

function lerFotosGuardadas(): Record<string, string | null> {
  try {
    return armazem.lerGuardado<Record<string, string | null>>(GUARDADO) ?? {};
  } catch {
    return {};
  }
}

function guardarFotos() {
  gravacao = null;
  try {
    armazem.guardar(GUARDADO, Object.fromEntries([...fotos].filter(([, url]) => url))); // "sem foto" pergunta de novo
  } catch {
    // sem espaço ou banco local indisponível: fica só na memória
  }
}
const ouvintes = new Map<string, Set<() => void>>();
let fila = new Set<string>();
let agendado: ReturnType<typeof setTimeout> | null = null;

async function buscar() {
  agendado = null;
  const pedidos = [...fila];
  fila = new Set();
  for (let i = 0; i < pedidos.length; i += 100) {
    const lote = pedidos.slice(i, i + 100);
    let resposta: Record<string, string> = {};
    try {
      resposta = await api.fotos(lote);
    } catch {
      // sem internet ou API fora: fica a miniatura
    }
    for (const id of lote) {
      const url = resposta[id] ?? null;
      fotos.set(id, url);
      ouvintes.get(id)?.forEach((f) => f());
      ouvintes.delete(id);
    }
  }
  gravacao ??= setTimeout(guardarFotos, 2000);
}

/** Endereço da foto do produto (null = sem foto), pedido em lote junto com as outras miniaturas da tela. */
export function useFotoDeTeste(produtoId: string | null | undefined): string | null {
  const [, renovar] = useState(0);
  useEffect(() => {
    if (!MODO_TESTE || !produtoId || fotos.has(produtoId)) return;
    const ouvir = () => renovar((n) => n + 1);
    const lista = ouvintes.get(produtoId) ?? new Set();
    lista.add(ouvir);
    ouvintes.set(produtoId, lista);
    fila.add(produtoId);
    agendado ??= setTimeout(buscar, 60);
    return () => {
      ouvintes.get(produtoId)?.delete(ouvir);
    };
  }, [produtoId]);
  return MODO_TESTE && produtoId ? (fotos.get(produtoId) ?? null) : null;
}
