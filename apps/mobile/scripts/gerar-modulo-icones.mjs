/**
 * Transforma os SVGs baixados do Figma (assets/icones e assets/categorias) em src/componentes/icones.gerado.ts.
 * A cor do traço vira currentColor: quem desenha escolhe o token (claro/escuro). O desenho não é alterado.
 *
 *   npm run modulo-icones
 */
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");

function ler(pasta) {
  const saida = {};
  for (const arquivo of readdirSync(join(RAIZ, "assets", pasta)).filter((a) => a.endsWith(".svg")).sort()) {
    const svg = readFileSync(join(RAIZ, "assets", pasta, arquivo), "utf-8")
      .replace(/\s(style|id|preserveAspectRatio|overflow)="[^"]*"/g, "") // atributos de exportação que o react-native-svg não usa
      .replace(/stroke="#[0-9A-Fa-f]{6}"/g, 'stroke="currentColor"')
      .replace(/\s*\n\s*/g, "");
    saida[basename(arquivo, ".svg")] = svg;
  }
  return saida;
}

const icones = ler("icones");
const categorias = ler("categorias");
const corpo = `// Gerado por scripts/gerar-modulo-icones.mjs a partir dos SVGs do Figma. Não edite à mão.
export const ICONES = ${JSON.stringify(icones, null, 2)} as const;

export const ICONES_DE_CATEGORIA = ${JSON.stringify(categorias, null, 2)} as const;
`;
writeFileSync(join(RAIZ, "src", "componentes", "icones.gerado.ts"), corpo, "utf-8");
console.log(`${Object.keys(icones).length} ícones e ${Object.keys(categorias).length} categorias`);
