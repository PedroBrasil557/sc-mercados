"""Gera tema.ts a partir de tokens.json (exportado das variáveis do Figma).

Uso: python gerar_tema.py
"""
import json
from pathlib import Path

AQUI = Path(__file__).parent


def bloco(d, ind=2):
    pad = " " * ind
    linhas = []
    for k, v in d.items():
        if isinstance(v, dict):
            linhas.append(f"{pad}{k}: {{\n{bloco(v, ind + 2)}\n{pad}}},")
        elif isinstance(v, list):
            linhas.append(f"{pad}{k}: [{', '.join(str(x) for x in v)}] as const,")
        elif isinstance(v, str):
            linhas.append(f"{pad}{k}: {json.dumps(v, ensure_ascii=False)},")
        else:
            linhas.append(f"{pad}{k}: {v},")
    return "\n".join(linhas)


def main():
    t = json.loads((AQUI / "tokens.json").read_text(encoding="utf-8"))
    claro = {k: v["valores"]["Claro"] for k, v in t["cor"].items()}
    escuro = {k: v["valores"]["Escuro"] for k, v in t["cor"].items()}
    nomes = "\n".join(f" *   {k} = {v['nome']}" for k, v in t["cor"].items())
    categorias = sorted({v["nome"].split("/")[1] for v in t["cor"].values() if v["nome"].startswith("categoria/")})
    src = f"""/**
 * Tokens do Quanto Fica, exportados do Figma (variáveis).
 * Fonte da verdade: arquivo "Quanto Fica — App MVP", página "Fundamentos e componentes".
 * Não edite à mão: mude no Figma, atualize tokens.json e rode `python gerar_tema.py`.
 *
 * Nome no Figma → nome no código:
{nomes}
 */

export const corClaro = {{
{bloco(claro)}
}} as const;

export const corEscuro: Record<keyof typeof corClaro, string> = {{
{bloco(escuro)}
}};

/** Categorias da miniatura do produto (fundo + tinta de cada uma). */
export const categorias = {json.dumps(categorias, ensure_ascii=False)} as const;
export type Categoria = (typeof categorias)[number];

/** Escala de 4 dp: espaco1 = 4, espaco2 = 8 ... espaco8 = 32. */
export const medida = {{
{bloco(t["medida"])}
}} as const;

/** Durações em ms; curvas como cubic-bezier (x1, y1, x2, y2). */
export const movimento = {{
{bloco(t["movimento"])}
}};

export const tipografia = {{
{bloco(t["tipografia"])}
}} as const;

export type ModoTema = "claro" | "escuro";
export type Cor = keyof typeof corClaro;

export function tema(modo: ModoTema) {{
  return {{ cor: modo === "escuro" ? corEscuro : corClaro, medida, movimento, tipografia }};
}}
"""
    (AQUI / "tema.ts").write_text(src, encoding="utf-8")
    print(f"tema.ts: {len(claro)} cores, {len(categorias)} categorias")


if __name__ == "__main__":
    main()
