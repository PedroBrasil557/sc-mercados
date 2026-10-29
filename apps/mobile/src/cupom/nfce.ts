/**
 * Leitura do cupom fiscal (NFC-e) no próprio celular.
 *
 * O QR do cupom aponta para a consulta pública da Sefaz. A página abre dentro do app (a pessoa está
 * olhando: se a Sefaz pedir "não sou robô", é ela quem toca; o app nunca contorna a verificação).
 * O script abaixo lê só emitente, CNPJ do emitente, data, total e itens. O CPF do consumidor não é
 * lido em nenhum momento, então não tem como sair do celular.
 */

export type ItemLido = { descricao: string; codigo: string; quantidade: number; valor_total_centavos: number };
export type CupomExtraido = {
  emitente: string | null;
  cnpj: string | null;
  emitido_em: string; // AAAA-MM-DD
  total_centavos: number;
  itens: ItemLido[];
};

/** Chave de acesso (44 dígitos) a partir do texto do QR (URL com ?p=CHAVE|2|1|...) ou de uma chave digitada. */
export function extrairChave(texto: string): string | null {
  const p = /[?&]p=([^&|]+)/.exec(texto)?.[1];
  const candidatos = [p, texto].filter((t): t is string => !!t).map((t) => decodeURIComponent(t).replace(/\D/g, ""));
  for (const c of candidatos) {
    if (c.length === 44) return c;
    const achado = /\d{44}/.exec(c);
    if (achado) return achado[0];
  }
  return null;
}

/** Endereço da consulta: o próprio QR quando é um link; com a chave digitada, a consulta da Sefaz de SC. */
export function enderecoDaConsulta(textoDoQr: string, chave: string): string {
  return /^https?:\/\//i.test(textoDoQr.trim()) ? textoDoQr.trim() : `https://sat.sef.sc.gov.br/nfce/consulta?p=${chave}`;
}

/** "1.234,56" → 123456 */
export function centavos(texto: string): number {
  const limpo = texto.replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".");
  const v = Number(limpo);
  return Number.isFinite(v) ? Math.round(v * 100) : 0;
}

/** "28/10/2026 10:21:33" → "2026-10-28" */
export function dataIso(texto: string): string | null {
  const m = /(\d{2})\/(\d{2})\/(\d{4})/.exec(texto);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : null;
}

/**
 * Script injetado na página da consulta. Usa o leiaute padrão da consulta de NFC-e (tabela #tabResult,
 * classes txtTit, RCod, Rqtd, valor, totalNumb) e tenta de novo a cada segundo, porque a página pode
 * passar por uma verificação antes de mostrar os itens.
 */
export const SCRIPT_DE_LEITURA = `
(function () {
  function texto(el) { return el ? (el.textContent || "").replace(/\\s+/g, " ").trim() : ""; }
  function enviar(dados) { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify(dados)); }
  var tentativas = 0;
  function ler() {
    tentativas++;
    var linhas = document.querySelectorAll("#tabResult tr");
    var itens = [];
    for (var i = 0; i < linhas.length; i++) {
      var l = linhas[i];
      var descricao = texto(l.querySelector(".txtTit"));
      var codigo = texto(l.querySelector(".RCod")).replace(/[^0-9A-Za-z]/g, "").replace(/^Codigo/i, "").replace(/^C.digo/i, "");
      var qtd = texto(l.querySelector(".Rqtd")).replace(/[^0-9,.]/g, "").replace(",", ".");
      var valor = texto(l.querySelector(".valor"));
      if (descricao && valor) itens.push({ descricao: descricao, codigo: codigo || "?", quantidade: Number(qtd) || 1, valor: valor });
    }
    if (itens.length) {
      var cabecalho = document.querySelector("#conteudo") || document.body;
      var total = texto(document.querySelector(".totalNumb.txtMax")) || texto(document.querySelector(".totalNumb"));
      var emitente = texto(document.querySelector(".txtTopo"));
      // Só o CNPJ do EMITENTE (cabeçalho da loja); o bloco do consumidor nunca é lido.
      var cnpj = (texto(cabecalho.querySelector(".text")).match(/\\d{2}\\.?\\d{3}\\.?\\d{3}\\/?\\d{4}-?\\d{2}/) || [""])[0];
      var emissao = (document.body.innerText.match(/Emiss.o:?\\s*(\\d{2}\\/\\d{2}\\/\\d{4})/) || ["", ""])[1];
      enviar({ ok: true, emitente: emitente, cnpj: cnpj, emissao: emissao, total: total, itens: itens });
      return;
    }
    if (tentativas < 90) setTimeout(ler, 1000);
    else enviar({ ok: false });
  }
  ler();
})();
true;
`;

type Bruto = { ok: boolean; emitente?: string; cnpj?: string; emissao?: string; total?: string; itens?: { descricao: string; codigo: string; quantidade: number; valor: string }[] };

/** Converte a mensagem da página no formato da API. Devolve null se a leitura falhou. */
export function converter(mensagem: string, hoje = new Date()): CupomExtraido | null {
  let bruto: Bruto;
  try {
    bruto = JSON.parse(mensagem) as Bruto;
  } catch {
    return null;
  }
  if (!bruto.ok || !bruto.itens?.length) return null;
  const itens = bruto.itens.map((i) => ({
    descricao: i.descricao.slice(0, 200),
    codigo: i.codigo.slice(0, 60),
    quantidade: i.quantidade > 0 ? i.quantidade : 1,
    valor_total_centavos: centavos(i.valor),
  }));
  const somaDosItens = itens.reduce((s, i) => s + i.valor_total_centavos, 0);
  return {
    emitente: bruto.emitente || null,
    cnpj: bruto.cnpj ? bruto.cnpj.replace(/\D/g, "") : null,
    emitido_em: dataIso(bruto.emissao ?? "") ?? hoje.toISOString().slice(0, 10),
    total_centavos: bruto.total ? centavos(bruto.total) : somaDosItens,
    itens,
  };
}
