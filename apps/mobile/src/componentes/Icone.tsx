import { SvgXml } from "react-native-svg";

import { ICONES, ICONES_DE_CATEGORIA } from "./icones.gerado";

export type NomeIcone = keyof typeof ICONES;
export type NomeCategoria = keyof typeof ICONES_DE_CATEGORIA;

// Tamanhos permitidos pelo design system (Figma: "Ícone de traço, grade de 24 dp").
type Tamanho = 16 | 20 | 24 | 32 | 40;

/** Ícone oficial do Figma, na cor do token pedido. Decorativo: o rótulo fica no elemento que o contém. */
export function Icone({ nome, cor, tamanho = 24 }: { nome: NomeIcone; cor: string; tamanho?: Tamanho }) {
  return <SvgXml xml={ICONES[nome]} width={tamanho} height={tamanho} color={cor} accessibilityElementsHidden importantForAccessibility="no" />;
}

/** Ícone da categoria (laticínios, café, grãos...), usado nas miniaturas dos produtos. */
export function IconeDeCategoria({ categoria, cor, tamanho = 20 }: { categoria: NomeCategoria; cor: string; tamanho?: Tamanho }) {
  return (
    <SvgXml
      xml={ICONES_DE_CATEGORIA[categoria]}
      width={tamanho}
      height={tamanho}
      color={cor}
      accessibilityElementsHidden
      importantForAccessibility="no"
    />
  );
}
