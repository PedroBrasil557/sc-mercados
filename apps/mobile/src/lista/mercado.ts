/**
 * O "seu mercado" da casa: escolhido pela família ou, sem escolha, o mais perto com preço do site.
 * Fica guardado no aparelho para as telas abrirem sem esperar a internet.
 */
import { useEffect, useSyncExternalStore } from "react";

import { api, type Mercados } from "@/api/cliente";

import * as armazem from "./armazem";

const CHAVE = "mercados";
let estado: Mercados | null = armazem.lerGuardado<Mercados>(CHAVE);
const ouvintes = new Set<() => void>();
let buscando: Promise<void> | null = null;

function mudar(m: Mercados): void {
  estado = m;
  armazem.guardar(CHAVE, m);
  ouvintes.forEach((f) => f());
}

export function atualizarMercados(): Promise<void> {
  buscando ??= api
    .mercados()
    .then(mudar)
    .catch(() => undefined) // sem internet: fica o que estava guardado
    .finally(() => {
      buscando = null;
    });
  return buscando;
}

export const seuMercadoId = (): string | null => estado?.seu_mercado?.loja_id ?? null;

export function useMercados(): Mercados | null {
  const m = useSyncExternalStore(
    (f) => {
      ouvintes.add(f);
      return () => ouvintes.delete(f);
    },
    () => estado,
  );
  useEffect(() => {
    void atualizarMercados();
  }, []);
  return m;
}

/** Troca o seu mercado (null = sempre o mais perto). Vale para a casa toda. */
export async function escolherMercado(lojaId: string | null): Promise<void> {
  mudar(await api.escolherMercado(lojaId));
}
