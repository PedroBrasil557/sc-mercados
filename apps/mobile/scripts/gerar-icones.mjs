/**
 * Gera os ícones e a tela de abertura do SC Mercados a partir do vetor do Figma
 * ("Quanto Fica — App MVP", componente "Ícone do app", 24:1360).
 *
 *   npm run icones
 *
 * Saídas em assets/ e, para a Play Store, em ../../docs/loja/.
 */
import { Buffer } from "node:buffer";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const AQUI = dirname(fileURLToPath(import.meta.url));
const ASSETS = join(AQUI, "..", "assets");
const LOJA = join(AQUI, "..", "..", "..", "docs", "loja");

const AMARELO = "#FFD43B"; // marca/etiqueta
const VERDE = "#0F3B2E"; // fundo/profundo

// Desenho original numa área de 180 x 180 (exportado do Figma).
const ETIQUETA = "M49 93V57C49 54.8783 49.8429 52.8434 51.3431 51.3431C52.8434 49.8429 54.8783 49 57 49H93L135 91L91 135L49 93Z";
const FURO = "M70 78C74.4183 78 78 74.4183 78 70C78 65.5817 74.4183 62 70 62C65.5817 62 62 65.5817 62 70C62 74.4183 65.5817 78 70 78Z";
const CHECK = "M83 105L93 115L115 89";
const CENTRO = 92; // centro visual da etiqueta (49..135)

/** Desenho em `lado` px; `escala` = quanto da área os 180 pontos originais ocupam. */
function svg({ lado, escala = 1, fundo = null, raio = 0, cores = { etiqueta: VERDE, check: AMARELO }, mono = false }) {
  const k = (lado * escala) / 180;
  const deslocamento = lado / 2 - CENTRO * k;
  const arte = mono
    ? `<mask id="m"><rect width="180" height="180" fill="white"/><path d="${CHECK}" stroke="black" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></mask>
       <path d="${ETIQUETA}" fill="white" mask="url(#m)"/>`
    : `<path d="${ETIQUETA}" fill="${cores.etiqueta}"/><path d="${FURO}" fill="${cores.etiqueta}"/>
       <path d="${CHECK}" stroke="${cores.check}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`;
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${lado}" height="${lado}" viewBox="0 0 ${lado} ${lado}">
    ${fundo ? `<rect width="${lado}" height="${lado}" rx="${raio}" fill="${fundo}"/>` : ""}
    <g transform="translate(${deslocamento} ${deslocamento}) scale(${k})">${arte}</g></svg>`);
}

async function png(nome, buffer, pasta = ASSETS) {
  mkdirSync(pasta, { recursive: true });
  await sharp(buffer).png({ compressionLevel: 9 }).toFile(join(pasta, nome));
  console.log("gerado", join(pasta, nome).replace(join(AQUI, "..", "..", ".."), "."));
}

// Ícone quadrado cheio (o sistema arredonda os cantos): mesma proporção do Figma.
await png("icon.png", svg({ lado: 1024, fundo: AMARELO }));
// Android adaptável: frente na zona segura (círculo central de 66%), fundo só a cor amarela (app.json).
await png("android-icon-foreground.png", svg({ lado: 1024, escala: 0.76 }));
await png("android-icon-background.png", svg({ lado: 1024, escala: 0, fundo: AMARELO }));
// Ícone temático do Android 13+: silhueta numa cor só, com o check vazado.
await png("android-icon-monochrome.png", svg({ lado: 1024, escala: 0.76, mono: true }));
// Abertura: o ícone arredondado, como no Figma, sobre o fundo verde configurado no app.json.
await png("splash-icon.png", svg({ lado: 1024, fundo: AMARELO, raio: (42 / 180) * 1024 }));
await png("favicon.png", svg({ lado: 48, fundo: AMARELO, raio: 11 }));
// Play Store: ícone de 512 x 512, quadrado cheio (a loja aplica a máscara).
await png("icone-512.png", svg({ lado: 512, fundo: AMARELO }), LOJA);
