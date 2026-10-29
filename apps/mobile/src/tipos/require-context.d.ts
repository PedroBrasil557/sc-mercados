// require.context do Metro (o Expo Router o liga). O tipo vem do servidor do Expo em .expo/types, que não
// existe no CI; esta declaração deixa o tsc igual nos dois lugares.
interface ContextoDeArquivos {
  keys(): string[];
  (id: string): unknown;
}

interface NodeRequire {
  context(pasta: string, subpastas?: boolean, filtro?: RegExp): ContextoDeArquivos;
}
