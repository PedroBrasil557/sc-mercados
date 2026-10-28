/**
 * Banco local do aparelho (SQLite): a lista funciona sem internet.
 *
 * Toda mudança vira uma operação gravada aqui primeiro (enviada = 0) e aparece na tela na hora.
 * A sincronia envia as pendentes e traz as dos outros aparelhos da casa.
 */
import * as SQLite from "expo-sqlite";

import type { Operacao, Produto } from "@/api/cliente";

const db = SQLite.openDatabaseSync("scmercados.db");

// Cada passo roda uma vez; a versão fica no próprio SQLite (PRAGMA user_version).
const MIGRACOES = [
  `create table operacao (
     id text primary key, lista_id text not null, item_id text not null, tipo text not null,
     valor real, feita_em text not null, membro_id text, produto_id text, categoria_id text,
     enviada integer not null default 0, seq integer);
   create index operacao_lista on operacao (lista_id, enviada);
   create table item_info (item_id text primary key, lista_id text not null, produto_id text, nome text, marca text, categoria text);
   create table cursor (lista_id text primary key, seq integer not null);
   create table sessao (chave text primary key, valor text not null);
   create table produto_cache (id text primary key, nome text not null, marca text, tamanho text, unidade text, categoria text not null);`,
];

const versao = db.getFirstSync<{ user_version: number }>("pragma user_version")?.user_version ?? 0;
for (let v = versao; v < MIGRACOES.length; v++) {
  db.withTransactionSync(() => {
    db.execSync(MIGRACOES[v]!);
    db.execSync(`pragma user_version = ${v + 1}`);
  });
}

// ---------- Sessão (quem é este aparelho) ----------

export type Sessao = { membro_id: string; casa_id: string; lista_id: string; apelido: string; nomes: Record<string, string> };

export function lerSessao(): Sessao | null {
  const linha = db.getFirstSync<{ valor: string }>("select valor from sessao where chave = 'sessao'");
  return linha ? (JSON.parse(linha.valor) as Sessao) : null;
}

export function gravarSessao(s: Sessao): void {
  db.runSync("insert or replace into sessao (chave, valor) values ('sessao', ?)", JSON.stringify(s));
}

export function apagarTudo(): void {
  db.execSync("delete from operacao; delete from item_info; delete from cursor; delete from sessao;");
}

// ---------- Operações ----------

type LinhaOperacao = {
  id: string;
  item_id: string;
  tipo: Operacao["tipo"];
  valor: number | null;
  feita_em: string;
  membro_id: string | null;
  produto_id: string | null;
  categoria_id: string | null;
};

export function gravarLocal(listaId: string, op: Operacao): void {
  db.runSync(
    `insert or ignore into operacao (id, lista_id, item_id, tipo, valor, feita_em, membro_id, produto_id, categoria_id, enviada)
     values (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)`,
    op.id, listaId, op.item_id, op.tipo, op.valor ?? null, op.feita_em, op.membro_id ?? null, op.produto_id ?? null, op.categoria_id ?? null,
  );
}

/** Operações vindas do servidor: as que já temos só ganham o número de sequência. */
export function gravarRecebidas(listaId: string, ops: (Operacao & { seq: number })[], cursor: number): void {
  db.withTransactionSync(() => {
    for (const op of ops) {
      db.runSync(
        `insert into operacao (id, lista_id, item_id, tipo, valor, feita_em, membro_id, enviada, seq)
         values (?, ?, ?, ?, ?, ?, ?, 1, ?)
         on conflict (id) do update set enviada = 1, seq = excluded.seq`,
        op.id, listaId, op.item_id, op.tipo, op.valor ?? null, op.feita_em, op.membro_id ?? null, op.seq,
      );
    }
    db.runSync("insert or replace into cursor (lista_id, seq) values (?, ?)", listaId, cursor);
  });
}

export function pendentes(listaId: string): Operacao[] {
  return db
    .getAllSync<LinhaOperacao>(
      "select id, item_id, tipo, valor, feita_em, membro_id, produto_id, categoria_id from operacao where lista_id = ? and enviada = 0 order by feita_em, id",
      listaId,
    )
    .map((o) => ({ ...o, valor: o.valor ?? undefined, produto_id: o.produto_id ?? undefined, categoria_id: o.categoria_id ?? undefined }));
}

export function marcarEnviadas(ids: string[]): void {
  db.withTransactionSync(() => {
    for (const id of ids) db.runSync("update operacao set enviada = 1 where id = ?", id);
  });
}

export function todas(listaId: string): Operacao[] {
  return db.getAllSync<LinhaOperacao>("select id, item_id, tipo, valor, feita_em, membro_id from operacao where lista_id = ?", listaId);
}

export function cursor(listaId: string): number {
  return db.getFirstSync<{ seq: number }>("select seq from cursor where lista_id = ?", listaId)?.seq ?? 0;
}

// ---------- Nome de cada item (para mostrar sem internet) ----------

export type InfoDoItem = { item_id: string; produto_id: string | null; nome: string | null; marca: string | null; categoria: string | null };

export function gravarInfo(listaId: string, info: InfoDoItem[]): void {
  db.withTransactionSync(() => {
    for (const i of info) {
      db.runSync(
        "insert or replace into item_info (item_id, lista_id, produto_id, nome, marca, categoria) values (?, ?, ?, ?, ?, ?)",
        i.item_id, listaId, i.produto_id, i.nome, i.marca, i.categoria,
      );
    }
  });
}

export function infos(listaId: string): Map<string, InfoDoItem> {
  const linhas = db.getAllSync<InfoDoItem>("select item_id, produto_id, nome, marca, categoria from item_info where lista_id = ?", listaId);
  return new Map(linhas.map((l) => [l.item_id, l]));
}

// ---------- Catálogo guardado (busca sem internet) ----------

export function guardarCatalogo(produtos: Produto[]): void {
  db.withTransactionSync(() => {
    for (const p of produtos) {
      db.runSync(
        "insert or replace into produto_cache (id, nome, marca, tamanho, unidade, categoria) values (?, ?, ?, ?, ?, ?)",
        p.id, p.nome, p.marca, p.tamanho, p.unidade, p.categoria,
      );
    }
  });
}

const semAcento = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function buscarNoCatalogo(busca: string): Produto[] {
  const palavras = semAcento(busca).split(/\s+/).filter(Boolean);
  const produtos = db.getAllSync<Produto>("select id, nome, marca, tamanho, unidade, categoria from produto_cache order by categoria, nome");
  return produtos.filter((p) => palavras.every((w) => semAcento(`${p.nome} ${p.marca ?? ""}`).includes(w)));
}
