/** Dados da API guardados no celular: a tela abre na hora com o último que veio e atualiza quando a internet responde. */
import { useCallback, useEffect, useState } from "react";

import * as armazem from "./armazem";

export function useGuardado<T>(chave: string, buscar: () => Promise<T>): { dados: T | null; carregando: boolean; semConexao: boolean; atualizar: () => void } {
  const [dados, setDados] = useState<T | null>(() => armazem.lerGuardado<T>(chave));
  const [carregando, setCarregando] = useState(true);
  const [semConexao, setSemConexao] = useState(false);
  const [vez, setVez] = useState(0);

  useEffect(() => {
    let valido = true;
    buscar()
      .then((d) => {
        armazem.guardar(chave, d);
        if (valido) {
          setDados(d);
          setSemConexao(false);
        }
      })
      .catch(() => valido && setSemConexao(true))
      .finally(() => valido && setCarregando(false));
    return () => {
      valido = false;
    };
    // `buscar` muda a cada render; quem pede de novo é `vez` (puxar para atualizar)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave, vez]);

  const atualizar = useCallback(() => {
    setCarregando(true);
    setVez((v) => v + 1);
  }, []);
  return { dados, carregando, semConexao, atualizar };
}
