/**
 * Gera os ícones e a tela de abertura do SC Mercados a partir do glifo do Figma
 * ("Quanto Fica — App MVP", página "Marca — final (B)", componente "Marca/Glifo Sᶜ", 97:408).
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

// Glifo Sᶜ numa área de 715,37 x 600 (exportado do Figma). S = reais (altura 600),
// C = centavos (0,42 da altura), sublinhado na espinha do S.
const LARGURA = 715.37;
const ALTURA = 600;
const S = "M240.891 600C200.194 600 164.438 595.349 133.624 586.047C103.391 576.744 78.1008 563.372 57.7519 545.93C37.4031 528.488 22.2868 507.558 12.4031 483.14C3.10078 458.14 -0.968992 430.523 0.193799 400.291L131.008 371.512C132.171 398.256 137.694 420.058 147.578 436.919C158.043 453.198 171.996 465.407 189.438 473.547C206.88 481.105 226.357 484.884 247.868 484.884C265.31 484.884 280.717 482.849 294.089 478.779C307.461 474.128 317.926 468.023 325.484 460.465C333.624 452.326 337.694 443.023 337.694 432.558C337.694 418.605 332.461 407.267 321.996 398.547C311.531 389.244 296.996 381.395 278.391 375C260.368 368.605 239.729 362.209 216.473 355.814C191.473 348.837 166.473 341.279 141.473 333.14C117.054 324.419 94.6705 313.663 74.3217 300.872C53.9729 288.081 37.4031 271.512 24.6124 251.163C12.4031 230.814 6.29845 205.523 6.29845 175.291C6.29845 138.081 15.6008 106.395 34.2054 80.2326C53.3915 54.0698 79.5543 34.3023 112.694 20.9302C146.415 6.97674 184.787 0 227.81 0C273.159 0 313.566 7.84884 349.031 23.5465C384.496 38.6628 411.822 61.0465 431.008 90.6977C450.194 120.349 457.752 156.686 453.682 199.709L324.612 220.64C325.194 203.198 323.45 187.791 319.38 174.419C315.31 161.047 308.915 149.709 300.194 140.407C292.054 131.105 281.589 124.128 268.798 119.477C256.008 114.244 240.891 111.628 223.45 111.628C205.426 111.628 190.31 113.953 178.101 118.605C166.473 123.256 157.461 129.651 151.066 137.791C145.252 145.93 142.345 155.233 142.345 165.698C142.345 177.907 146.996 188.081 156.298 196.221C165.601 204.36 178.973 211.628 196.415 218.023C213.857 223.837 234.496 229.942 258.333 236.337C283.333 243.314 308.333 251.163 333.333 259.884C358.915 268.023 382.461 279.07 403.973 293.023C425.484 306.395 442.636 323.837 455.426 345.349C468.798 366.86 475.484 394.186 475.484 427.326C475.484 465.698 465.31 497.674 444.961 523.256C425.194 548.837 397.578 568.023 362.112 580.814C327.229 593.605 286.822 600 240.891 600Z";
const C = "M614.862 252C594.351 252 576.769 248.704 562.118 242.11C547.467 235.517 535.502 226.36 526.223 214.64C516.944 202.919 510.107 189.61 505.711 174.715C501.56 159.576 499.484 143.581 499.484 126.733C499.484 109.395 501.682 93.0349 506.078 77.6512C510.473 62.2674 517.188 48.8372 526.223 37.3605C535.502 25.6395 547.345 16.4826 561.752 9.88954C576.159 3.29651 593.496 0 613.764 0C631.345 0 646.484 2.56395 659.182 7.69185C671.88 12.5756 682.014 19.4128 689.583 28.2035C697.397 36.75 702.769 46.6395 705.7 57.8721C708.63 69.1046 709.362 80.8256 707.897 93.0349L653.322 99.6279C653.81 89.1279 652.467 80.093 649.293 72.5233C646.362 64.9535 641.723 59.093 635.374 54.9419C629.269 50.7907 621.455 48.7151 611.932 48.7151C603.874 48.7151 596.671 50.3023 590.322 53.4767C584.217 56.6512 578.967 61.4128 574.572 67.7616C570.421 74.1105 567.246 82.0465 565.048 91.5698C562.851 100.849 561.752 111.715 561.752 124.169C561.752 140.285 563.705 154.326 567.612 166.291C571.519 178.012 577.502 187.169 585.56 193.762C593.618 200.11 603.752 203.285 615.961 203.285C627.194 203.285 635.984 200.721 642.333 195.593C648.926 190.465 653.566 183.384 656.252 174.349C658.938 165.314 659.793 155.18 658.816 143.948L714.857 148.709C716.078 162.14 715.101 175.081 711.926 187.535C708.996 199.744 703.502 210.733 695.444 220.5C687.63 230.267 677.008 237.959 663.578 243.576C650.391 249.192 634.153 252 614.862 252Z";
const SUBLINHADO = '<rect x="499.484" y="276" width="215.881" height="36" rx="7.2"/>';

// Altura do S em relação ao lado: 520/1024 no ícone cheio; 400/1024 na frente do Android (zona segura 66/108).
const CHEIO = 520 / 1024;
const ZONA_SEGURA = 400 / 1024;

/** Desenho em `lado` px com o S ocupando `altura` do lado, centrado com a correção ótica do Figma (+2% x, +1,5% y). */
function svg({ lado, altura = CHEIO, fundo = null, raio = 0, cor = AMARELO }) {
  const k = (lado * altura) / ALTURA;
  const x = (lado - LARGURA * k) / 2 + 0.02 * LARGURA * k;
  const y = (lado - ALTURA * k) / 2 + 0.015 * ALTURA * k;
  const arte = altura ? `<g fill="${cor}" transform="translate(${x} ${y}) scale(${k})"><path d="${S}"/><path d="${C}"/>${SUBLINHADO}</g>` : "";
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${lado}" height="${lado}" viewBox="0 0 ${lado} ${lado}">
    ${fundo ? `<rect width="${lado}" height="${lado}" rx="${raio}" fill="${fundo}"/>` : ""}${arte}</svg>`);
}

async function png(nome, buffer, pasta = ASSETS) {
  mkdirSync(pasta, { recursive: true });
  await sharp(buffer).png({ compressionLevel: 9 }).toFile(join(pasta, nome));
  console.log("gerado", join(pasta, nome).replace(join(AQUI, "..", "..", ".."), "."));
}

// Ícone quadrado cheio (o sistema arredonda os cantos): "Ícone/Mestre — claro" do Figma.
await png("icon.png", svg({ lado: 1024, fundo: VERDE }));
// Android adaptável: frente na zona segura, fundo só o verde (app.json).
await png("android-icon-foreground.png", svg({ lado: 1024, altura: ZONA_SEGURA }));
await png("android-icon-background.png", svg({ lado: 1024, altura: 0, fundo: VERDE }));
// Ícone temático do Android 13+: silhueta branca, o sistema aplica a cor do tema.
await png("android-icon-monochrome.png", svg({ lado: 1024, altura: ZONA_SEGURA, cor: "#FFFFFF" }));
// Abertura: só o glifo, sobre o fundo verde configurado no app.json.
await png("splash-icon.png", svg({ lado: 1024 }));
await png("favicon.png", svg({ lado: 48, fundo: VERDE, raio: 11 }));
// Play Store: ícone de 512 x 512, quadrado cheio (a loja aplica a máscara).
await png("icone-512.png", svg({ lado: 512, fundo: VERDE }), LOJA);
