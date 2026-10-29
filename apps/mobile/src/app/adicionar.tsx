/** R3/R4 Busca: entende o tipo ("açúcar" não traz "zero açúcar"), mostra primeiro "qualquer marca" e depois
 * marcas e tamanhos com o preço no seu mercado e por kg/l. Filtros: onde comprar, ordem, tipo, tamanho, marca. */
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Busca, type FiltrosDaBusca, type GrupoQualquerMarca, type Produto, type ResultadoDaBusca } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Chip } from "@/componentes/Chip";
import { confirmar } from "@/componentes/Confirmacao";
import { Icone } from "@/componentes/Icone";
import { LeitorDeCodigo } from "@/componentes/LeitorDeCodigo";
import { Miniatura } from "@/componentes/Miniatura";
import { PainelInferior } from "@/componentes/PainelInferior";
import { SeletorDeMercado } from "@/componentes/SeletorDeMercado";
import { km, reais, tamanho } from "@/formatar";
import { adicionarProduto, buscarProdutos, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

const ORDENS: { valor: NonNullable<FiltrosDaBusca["ordem"]>; nome: string }[] = [
  { valor: "relevancia", nome: "Mais relevante" },
  { valor: "preco", nome: "Menor preço" },
  { valor: "preco_unidade", nome: "Menor preço por kg" },
  { valor: "desconto", nome: "Maior desconto" },
];
const ONDE: { valor: NonNullable<FiltrosDaBusca["onde"]>; nome: string }[] = [
  { valor: "seu", nome: "Seu mercado" },
  { valor: "perto", nome: "Perto de mim (até 5 km)" },
  { valor: "todos", nome: "Qualquer mercado" },
];

function produtoDe(r: ResultadoDaBusca): Produto {
  return { id: r.produto_id, nome: r.nome, nome_curto: r.nome_curto, marca: r.marca, tamanho: r.tamanho, unidade: r.unidade, categoria: r.categoria };
}

/** O grupo guarda o tamanho na chave ("feijao carioca|1000g"): a miniatura da lista mostra "1 kg". */
function produtoDoGrupo(g: GrupoQualquerMarca): Produto {
  const m = /\|([\d.]+)(g|ml|un)$/.exec(g.grupo);
  return {
    id: g.produto_id,
    nome: g.nome,
    nome_curto: g.nome.split(" · ")[0] ?? g.nome,
    marca: null,
    tamanho: m ? m[1]! : null,
    unidade: m ? m[2]! : null,
    categoria: g.categoria,
  };
}

function contarFiltros(f: FiltrosDaBusca): number {
  return [f.onde && f.onde !== "todos", f.ordem && f.ordem !== "relevancia", f.tipo, f.tamanho, f.marca, f.oferta, f.rede?.length].filter(Boolean).length;
}

export default function Adicionar() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const params = useLocalSearchParams<{ busca?: string }>();
  const { itens } = useLista();
  const [busca, setBusca] = useState(params.busca ?? "");
  const [filtros, setFiltros] = useState<FiltrosDaBusca>({});
  const [resultado, setResultado] = useState<Busca | null>(null);
  const [semConexao, setSemConexao] = useState<Produto[] | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [lendo, setLendo] = useState(false);
  const [painel, setPainel] = useState(false);

  useEffect(() => {
    let valido = true;
    const termo = busca.trim();
    const espera = setTimeout(() => {
      setCarregando(true);
      api
        .busca(termo, filtros)
        .then((r) => {
          if (!valido) return;
          setResultado(r);
          setSemConexao(null);
        })
        .catch(async () => {
          // Sem internet: busca no catálogo guardado no celular, sem os preços de hoje.
          const local = await buscarProdutos(termo);
          if (valido) setSemConexao(local.produtos);
        })
        .finally(() => valido && setCarregando(false));
    }, 250);
    return () => {
      valido = false;
      clearTimeout(espera);
    };
  }, [busca, filtros]);

  const naLista = (produtoId: string, qualquerMarca: boolean) =>
    itens.find((i) => i.produto_id === produtoId && i.qualquer_marca === qualquerMarca && !i.comprado);
  const mudar = (parcial: Partial<FiltrosDaBusca>) => setFiltros((f) => ({ ...f, ...parcial }));
  const alternar = <K extends keyof FiltrosDaBusca>(k: K, v: FiltrosDaBusca[K]) => mudar({ [k]: filtros[k] === v ? undefined : v } as Partial<FiltrosDaBusca>);
  const pôr = (p: Produto, qualquerMarca = false) => {
    adicionarProduto(p, { qualquerMarca });
    confirmar(`Na lista: ${p.nome_curto ?? p.nome}${qualquerMarca ? " (qualquer marca)" : ""}`);
  };
  const ativos = contarFiltros(filtros);
  const termo = busca.trim();
  const tiposRapidos = useMemo(() => (resultado?.filtros.tipos ?? []).slice(0, 3), [resultado]);

  const cabecalho = (
    <View style={{ gap: 12, paddingBottom: 8 }}>
      <SeletorDeMercado prefixo="Preços do seu mercado" />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={estilos.chips} keyboardShouldPersistTaps="handled">
        <Chip texto={ativos ? `Filtros · ${ativos}` : "Filtros"} ativo={ativos > 0} aoTocar={() => setPainel(true)} />
        <Chip texto="Seu mercado" ativo={filtros.onde === "seu"} aoTocar={() => alternar("onde", "seu")} />
        <Chip texto="Em oferta" ativo={!!filtros.oferta} aoTocar={() => mudar({ oferta: !filtros.oferta })} />
        <Chip texto="Menor preço por kg" ativo={filtros.ordem === "preco_unidade"} aoTocar={() => alternar("ordem", "preco_unidade")} />
        {tiposRapidos.map((t) => (
          <Chip key={t.valor} texto={t.valor} ativo={filtros.tipo === t.valor} aoTocar={() => alternar("tipo", t.valor)} />
        ))}
      </ScrollView>
      {resultado && resultado.escondidos_zero > 0 && !filtros.mostrar_zero ? (
        <View style={[estilos.entendido, { backgroundColor: cor.fundoAfundado }]}>
          <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
            Escondemos {resultado.escondidos_zero} {resultado.escondidos_zero === 1 ? "produto" : "produtos"} “zero” ou “sem” {termo}.{" "}
            <Text accessibilityRole="button" onPress={() => mudar({ mostrar_zero: true })} style={{ color: cor.estadoEconomia }}>
              Mostrar mesmo assim
            </Text>
          </Text>
        </View>
      ) : null}
      {semConexao ? (
        <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>Sem internet: buscando no catálogo guardado no celular, sem os preços de hoje.</Text>
      ) : null}
      {!semConexao && resultado?.grupos.length ? (
        <View style={{ gap: 8 }}>
          <Text accessibilityRole="header" style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>
            Qualquer marca
          </Text>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>Ponha o tipo na lista e o app escolhe o mais barato do mercado na hora da compra.</Text>
          {resultado.grupos.map((g) => {
            const ja = naLista(g.produto_id, true);
            return (
              <View key={g.grupo} style={[estilos.grupo, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
                <View style={[estilos.brilho, { backgroundColor: cor.estadoEconomiaSuave }]}>
                  <Icone nome="brilho" cor={cor.estadoEconomia} tamanho={20} />
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{g.nome}</Text>
                  <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>
                    {ja ? `Na lista · ${ja.quantidade}` : `Qualquer marca · ${g.marcas} ${g.marcas === 1 ? "marca" : "marcas"}${g.no_seu_mercado ? " no seu mercado" : ""}`}
                  </Text>
                  <Text style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>
                    a partir de {reais(g.a_partir_centavos)}
                    {g.marca_mais_barata ? ` (${g.marca_mais_barata}${g.em_oferta ? ", em oferta" : ""})` : ""}
                  </Text>
                </View>
                <BotaoMais rotulo={`Pôr ${g.nome}, qualquer marca, na lista`} aoTocar={() => pôr(produtoDoGrupo(g), true)} />
              </View>
            );
          })}
        </View>
      ) : null}
      {!semConexao && resultado && resultado.produtos.length ? (
        <View style={estilos.titulo}>
          <Text accessibilityRole="header" style={[fonte("tituloSecao"), { color: cor.textoPrincipal, flex: 1 }]}>
            {termo ? `Marcas e tamanhos · ${resultado.total}` : "Produtos"}
          </Text>
          <Text accessibilityRole="button" onPress={() => setPainel(true)} style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>
            {ORDENS.find((o) => o.valor === (filtros.ordem ?? "relevancia"))?.nome} ▾
          </Text>
        </View>
      ) : null}
    </View>
  );

  return (
    <View style={[estilos.tela, { backgroundColor: cor.fundoTela, paddingTop: margem.top + 8 }]}>
      <View style={estilos.topo}>
        <Pressable accessibilityRole="button" accessibilityLabel="Voltar" hitSlop={8} onPress={() => router.back()} style={estilos.voltar}>
          <Icone nome="voltar" cor={cor.textoPrincipal} />
        </Pressable>
        <View style={[estilos.busca, { backgroundColor: cor.fundoSuperficie, borderColor: cor.estadoEconomia }]}>
          <Icone nome="buscar" cor={cor.textoSuave} />
          <TextInput
            autoFocus
            accessibilityLabel="Buscar produto"
            placeholder="O que está faltando em casa?"
            placeholderTextColor={cor.textoSuave}
            selectionColor={cor.estadoEconomia}
            value={busca}
            onChangeText={(t) => {
              setBusca(t);
              setFiltros((f) => ({ onde: f.onde, ordem: f.ordem, oferta: f.oferta })); // busca nova: tipo/tamanho/marca recomeçam
            }}
            returnKeyType="search"
            style={[fonte("corpoForte"), estilos.campo, { color: cor.textoPrincipal }]}
          />
          {carregando ? <ActivityIndicator color={cor.estadoEconomia} /> : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Ler o código de barras"
            onPress={() => setLendo(true)}
            style={[estilos.codigo, { backgroundColor: cor.fundoProfundo }]}
          >
            <Icone nome="codigo-barras" cor={cor.textoInverso} tamanho={20} />
          </Pressable>
        </View>
      </View>

      <LeitorDeCodigo
        visivel={lendo}
        aoFechar={() => setLendo(false)}
        aoAchar={(p) => {
          pôr(p);
          setBusca(p.nome);
        }}
      />

      {semConexao ? (
        <FlatList
          data={semConexao}
          keyExtractor={(p) => p.id}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={estilos.lista}
          ListHeaderComponent={cabecalho}
          renderItem={({ item }) => (
            <LinhaDeResultado
              nome={item.nome_curto ?? item.nome}
              detalhe={[item.marca, tamanho(item.tamanho, item.unidade)].filter(Boolean).join(" · ")}
              produto={item}
              aoPor={() => pôr(item)}
            />
          )}
        />
      ) : (
        <FlatList
          data={resultado?.produtos ?? []}
          keyExtractor={(p) => p.produto_id}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={estilos.lista}
          ListHeaderComponent={cabecalho}
          ListEmptyComponent={
            resultado && !carregando ? (
              <View style={{ gap: 12, paddingTop: 16 }}>
                <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>
                  {termo ? `Não achamos “${termo}”${ativos ? " com esses filtros" : ""}.` : "Busque pelo nome, pelo tipo ou pela marca."}
                </Text>
                {ativos ? <Botao rotulo="Limpar os filtros" tipo="contorno" aoTocar={() => setFiltros({})} /> : null}
              </View>
            ) : undefined
          }
          renderItem={({ item }) => {
            const ja = naLista(item.produto_id, false);
            const nota = item.desconto_pct
              ? `Oferta: −${item.desconto_pct}%${item.no_seu_mercado ? " no seu mercado" : ""}`
              : item.mais_barato_longe
                ? `${reais(item.no_seu_mercado && item.preco_centavos ? item.preco_centavos - item.mais_barato_longe.preco_centavos : 0)} mais barato no ${item.mais_barato_longe.rede} (${km(item.mais_barato_longe.distancia_km)})`
                : item.preco_centavos && !item.no_seu_mercado
                  ? "Não tem no seu mercado"
                  : null;
            return (
              <LinhaDeResultado
                nome={item.nome_curto}
                detalhe={[item.marca, item.tamanho_texto, item.preco_por_unidade].filter(Boolean).join(" · ")}
                nota={ja ? `Na lista · ${ja.quantidade}` : nota}
                notaDestaque={!!ja || !!item.desconto_pct}
                preco={item.preco_centavos}
                onde={item.no_seu_mercado ? "no seu mercado" : item.onde ? `${item.onde.rede} · ${km(item.onde.distancia_km)}` : null}
                produto={produtoDe(item)}
                aoPor={() => pôr(produtoDe(item))}
              />
            );
          }}
        />
      )}

      <PainelInferior
        visivel={painel}
        titulo={termo ? `Filtrar “${termo}”` : "Filtrar"}
        aoFechar={() => setPainel(false)}
        rodape={<Botao rotulo={resultado ? `Ver ${resultado.total} ${resultado.total === 1 ? "produto" : "produtos"}` : "Ver produtos"} aoTocar={() => setPainel(false)} largo />}
      >
        <View style={{ gap: 16 }}>
          <Grupo titulo="Onde comprar">
            {ONDE.map((o) => (
              <Chip key={o.valor} texto={o.nome} ativo={(filtros.onde ?? "todos") === o.valor} aoTocar={() => mudar({ onde: o.valor })} />
            ))}
          </Grupo>
          {resultado?.filtros.redes.length ? (
            <Grupo titulo="Só nestes mercados">
              {resultado.filtros.redes
                .filter((r) => r.tipo_preco !== "sem")
                .map((r) => {
                  const marcado = filtros.rede?.includes(r.rede) ?? false;
                  return (
                    <Chip
                      key={r.rede}
                      texto={`${r.rede} · ${km(r.distancia_km)}${r.tipo_preco === "encarte" ? " · encarte" : ""}`}
                      ativo={marcado}
                      aoTocar={() => mudar({ rede: marcado ? filtros.rede?.filter((x) => x !== r.rede) : [...(filtros.rede ?? []), r.rede] })}
                    />
                  );
                })}
            </Grupo>
          ) : null}
          <Grupo titulo="Ordenar por">
            {ORDENS.map((o) => (
              <Chip key={o.valor} texto={o.nome} ativo={(filtros.ordem ?? "relevancia") === o.valor} aoTocar={() => mudar({ ordem: o.valor })} />
            ))}
          </Grupo>
          {resultado?.filtros.tipos.length ? (
            <Grupo titulo="Tipo">
              {resultado.filtros.tipos.map((t) => (
                <Chip key={t.valor} texto={`${t.valor} · ${t.n}`} ativo={filtros.tipo === t.valor} aoTocar={() => alternar("tipo", t.valor)} />
              ))}
            </Grupo>
          ) : null}
          {resultado?.filtros.tamanhos.length ? (
            <Grupo titulo="Tamanho">
              {resultado.filtros.tamanhos.map((t) => (
                <Chip key={t.valor} texto={t.valor} ativo={filtros.tamanho === t.valor} aoTocar={() => alternar("tamanho", t.valor)} />
              ))}
            </Grupo>
          ) : null}
          {resultado?.filtros.marcas.length ? (
            <Grupo titulo="Marca">
              {resultado.filtros.marcas.map((t) => (
                <Chip key={t.valor} texto={t.valor} ativo={filtros.marca === t.valor} aoTocar={() => alternar("marca", t.valor)} />
              ))}
            </Grupo>
          ) : null}
          <Alavanca titulo="Só em oferta" detalhe="Preço caiu de verdade, conferido com os outros mercados" valor={!!filtros.oferta} aoMudar={(v) => mudar({ oferta: v })} />
          <Alavanca
            titulo="Esconder “zero” e “sem”"
            detalhe="Ex.: “zero açúcar” numa busca por açúcar"
            valor={!filtros.mostrar_zero}
            aoMudar={(v) => mudar({ mostrar_zero: !v })}
          />
          {ativos ? <Botao rotulo="Limpar tudo" tipo="contorno" aoTocar={() => setFiltros({})} /> : null}
        </View>
      </PainelInferior>
    </View>
  );
}

function LinhaDeResultado(p: {
  nome: string;
  detalhe: string;
  nota?: string | null;
  notaDestaque?: boolean;
  preco?: number | null;
  onde?: string | null;
  produto: Produto;
  aoPor: () => void;
}) {
  const { cor } = useTema();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${p.nome}, ${p.detalhe}${p.preco ? `, ${reais(p.preco)} ${p.onde ?? ""}` : ""}. Ver detalhes`}
      onPress={() => router.push({ pathname: "/produto/[id]", params: { id: p.produto.id } })}
      style={[estilos.resultado, { borderColor: cor.bordaPadrao }]}
    >
      <Miniatura categoria={p.produto.categoria} tamanho={tamanho(p.produto.tamanho, p.produto.unidade)} nome={p.nome} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text numberOfLines={2} style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>
          {p.nome}
        </Text>
        {p.detalhe ? (
          <Text numberOfLines={2} style={[fonte("legenda"), { color: cor.textoSuave }]}>
            {p.detalhe}
          </Text>
        ) : null}
        {p.nota ? (
          <Text numberOfLines={2} style={[fonte("legenda"), { color: p.notaDestaque ? cor.estadoEconomia : cor.textoSuave }]}>
            {p.nota}
          </Text>
        ) : null}
      </View>
      {p.preco ? (
        <View style={{ alignItems: "flex-end" }}>
          <Text style={[fonte("precoMedio"), { color: cor.textoPrincipal }]}>{reais(p.preco)}</Text>
          {p.onde ? <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{p.onde}</Text> : null}
        </View>
      ) : null}
      <BotaoMais rotulo={`Pôr ${p.nome} na lista`} aoTocar={p.aoPor} />
    </Pressable>
  );
}

function BotaoMais({ rotulo, aoTocar }: { rotulo: string; aoTocar: () => void }) {
  const { cor } = useTema();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={rotulo}
      hitSlop={6}
      onPress={aoTocar}
      style={({ pressed }) => [estilos.mais, { backgroundColor: cor.fundoProfundo }, pressed && { opacity: 0.85 }]}
    >
      <Icone nome="mais" cor={cor.textoInverso} tamanho={20} />
    </Pressable>
  );
}

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  const { cor } = useTema();
  return (
    <View style={{ gap: 8 }}>
      <Text style={[fonte("rotulo"), { color: cor.textoSuave }]}>{titulo}</Text>
      <View style={estilos.chipsQuebra}>{children}</View>
    </View>
  );
}

function Alavanca({ titulo, detalhe, valor, aoMudar }: { titulo: string; detalhe: string; valor: boolean; aoMudar: (v: boolean) => void }) {
  const { cor } = useTema();
  return (
    <View style={estilos.alavanca}>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{titulo}</Text>
        <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{detalhe}</Text>
      </View>
      <Switch
        accessibilityLabel={titulo}
        value={valor}
        onValueChange={aoMudar}
        trackColor={{ true: cor.estadoEconomia, false: cor.bordaForte }}
        thumbColor={cor.fundoSuperficie}
      />
    </View>
  );
}

const estilos = StyleSheet.create({
  tela: { flex: 1 },
  topo: { flexDirection: "row", alignItems: "center", gap: 8, paddingLeft: 12, paddingRight: 20, paddingBottom: 12 },
  voltar: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  busca: { flex: 1, height: 54, borderRadius: 27, borderWidth: 1.5, flexDirection: "row", alignItems: "center", gap: 10, paddingLeft: 16, paddingRight: 6 },
  codigo: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center" },
  campo: { flex: 1, paddingVertical: 0 },
  lista: { paddingHorizontal: 20, paddingBottom: 120 },
  chips: { gap: 8, paddingRight: 20 },
  chipsQuebra: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  entendido: { padding: 12, borderRadius: 14 },
  grupo: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12, paddingHorizontal: 16, borderRadius: 14, borderWidth: 1 },
  brilho: { width: 44, height: 44, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  titulo: { flexDirection: "row", alignItems: "center", gap: 8, paddingTop: 8 },
  resultado: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12, borderBottomWidth: 1 },
  mais: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
  alavanca: { flexDirection: "row", alignItems: "center", gap: 12 },
});
