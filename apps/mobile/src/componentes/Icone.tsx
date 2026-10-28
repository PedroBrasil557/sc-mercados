import Svg, { Path } from "react-native-svg";

// Traços do protótipo testado. A espessura segue o tamanho (ajuste óptico do Figma: 16→1.25, 20→1.5, 24→1.75).
const TRACOS = {
  inicio: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  lista: "M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01",
  comparar: "M12 3v18M5 7h14M5 7l-3 7a4 4 0 0 0 6 0zM19 7l-3 7a4 4 0 0 0 6 0z",
  ofertas: "M3 12V4h8l10 10-8 8z M7.5 7.5h.01",
  perfil: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
} as const;

export type NomeIcone = keyof typeof TRACOS;

const ESPESSURA: Record<16 | 20 | 24, number> = { 16: 1.25, 20: 1.5, 24: 1.75 };

export function Icone({ nome, cor, tamanho = 24 }: { nome: NomeIcone; cor: string; tamanho?: 16 | 20 | 24 }) {
  // O viewBox é 24: a espessura é convertida para que o traço tenha a largura óptica certa no tamanho exibido.
  const traco = (ESPESSURA[tamanho] * 24) / tamanho;
  return (
    <Svg width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" accessibilityElementsHidden importantForAccessibility="no">
      <Path d={TRACOS[nome]} stroke={cor} strokeWidth={traco} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}
