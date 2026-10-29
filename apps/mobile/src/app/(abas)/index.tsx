/** R1/R2 Início: a lista no seu mercado (e o porquê), o que a família fez, ofertas do seu mercado, o que está
 * acabando, encartes perto, a economia do mês e quando os preços foram conferidos. Nenhuma tela com uma coisa só. */
import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, type Comparacao, type Inicio as DadosDoInicio, type Oferta, type Produto } from "@/api/cliente";
import { Botao } from "@/componentes/Botao";
import { Chip } from "@/componentes/Chip";
import { CartaoDeOferta } from "@/componentes/CartaoDeOferta";
import { confirmar } from "@/componentes/Confirmacao";
import { Icone, type NomeIcone } from "@/componentes/Icone";
import { SeletorDeBairro } from "@/componentes/SeletorDeBairro";
import { SeletorDeMercado } from "@/componentes/SeletorDeMercado";
import { haQuanto, reais, seloDeFonte } from "@/formatar";
import { useComparacao } from "@/lista/comparacao";
import { useGuardado } from "@/lista/guardado";
import { adicionarProduto, trocarBairro, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

function saudacao(agora = new Date()): string {
  const h = agora.getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

/** "feijao carioca|1000g" -> tamanho e unidade, para a miniatura mostrar "1 kg". */
function doGrupo(grupo: string, produtoId: string, nome: string): Produto {
  const m = /\|([\d.]+)(g|ml|un)$/.exec(grupo);
  return { id: produtoId, nome, marca: null, tamanho: m ? m[1]! : null, unidade: m ? m[2]! : null, categoria: "mercearia" };
}

const TEXTO_DA_ATIVIDADE = { criar: "pôs", marcar: "comprou", remover: "tirou" } as const;

export default function Inicio() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao, itens } = useLista();
  const comparacao = useComparacao();
  const inicio = useGuardado<DadosDoInicio>("inicio", api.inicio);
  const ofertas = useGuardado<{ ofertas: Oferta[] }>("ofertas", api.ofertas);
  const [escolhendoBairro, setEscolhendoBairro] = useState(false);
  const aComprar = itens.filter((i) => !i.comprado);
  const membros = sessao ? Object.values(sessao.nomes) : [];
  const d = inicio.dados;
  const doSeuMercado = (ofertas.dados?.ofertas ?? []).filter((o) => o.seu_mercado).slice(0, 2);

  const pôr = (p: Produto, qualquerMarca: boolean, rotulo: string) => {
    adicionarProduto(p, { qualquerMarca });
    confirmar(`Na lista: ${rotulo}`);
  };

  return (
    <ScrollView
      style={{ backgroundColor: cor.fundoTela }}
      contentContainerStyle={[estilos.conteudo, { paddingTop: margem.top + 4 }]}
      refreshControl={
        <RefreshControl
          refreshing={inicio.carregando && !!d}
          onRefresh={() => {
            inicio.atualizar();
            ofertas.atualizar();
            comparacao.atualizar();
          }}
          colors={[cor.estadoEconomia]}
        />
      }
    >
      <View style={estilos.cabecalho}>
        <View style={{ flex: 1 }}>
          <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
            {saudacao()}
            {sessao?.apelido && sessao.apelido !== "Eu" ? `, ${sessao.apelido}` : ""}
          </Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Bairro: ${sessao?.bairro_nome ?? "não escolhido"}. Toque para trocar`}
            onPress={() => setEscolhendoBairro(true)}
            style={estilos.bairro}
          >
            <Text numberOfLines={1} style={[fonte("tituloTela"), { color: cor.textoPrincipal, flexShrink: 1 }]}>
              {sessao?.bairro_nome ?? "Escolha o bairro"}
            </Text>
            <View style={{ transform: [{ rotate: "90deg" }] }}>
              <Icone nome="seta-direita" cor={cor.textoPrincipal} tamanho={20} />
            </View>
          </Pressable>
        </View>
        <View style={estilos.casa} accessible accessibilityLabel={`Casa: ${membros.join(", ")}`}>
          {membros.slice(0, 3).map((nome, i) => (
            <View
              key={`${nome}-${i}`}
              style={[estilos.membro, { backgroundColor: i === 0 ? cor.marcaEtiqueta : cor.estadoEconomiaSuave, borderColor: cor.fundoTela, marginLeft: i ? -10 : 0 }]}
            >
              <Text style={[fonte("corpoForte"), { color: i === 0 ? cor.marcaSobreEtiqueta : cor.textoPrincipal }]}>{nome.charAt(0).toUpperCase()}</Text>
            </View>
          ))}
        </View>
      </View>

      {!sessao?.bairro_id ? (
        <View style={[estilos.cartaoGrande, { backgroundColor: cor.marcaEtiqueta }]}>
          <Text style={[fonte("tituloSecao"), { color: cor.marcaSobreEtiqueta }]}>Onde você mora?</Text>
          <Text style={[fonte("corpoMenor"), { color: cor.marcaSobreEtiqueta }]}>
            Com o bairro, o app escolhe o seu mercado e compara a lista nos mercados perto de você.
          </Text>
          <Botao rotulo="Escolher o bairro" largo aoTocar={() => setEscolhendoBairro(true)} />
        </View>
      ) : (
        <>
          <SeletorDeMercado />

          {aComprar.length ? (
            <CartaoDaLista comparacao={comparacao.dados} itens={aComprar.length} carregando={comparacao.carregando} semConexao={comparacao.semConexao} />
          ) : (
            <View style={[estilos.cartaoGrande, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao, borderWidth: 1 }]}>
              <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>{itens.length ? "Lista em dia" : "Comece a lista da casa"}</Text>
              <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>
                Toque no que está faltando. Cada um vale qualquer marca: o app pega o mais barato do seu mercado.
              </Text>
              <View style={estilos.chips}>
                {(d?.basicos ?? []).map((b) => (
                  <Chip key={b.grupo} texto={`+ ${b.nome}`} aoTocar={() => pôr(doGrupo(b.grupo, b.produto_id, b.nome), true, `${b.nome} (qualquer marca)`)} />
                ))}
              </View>
              <Pressable
                accessibilityRole="button"
                onPress={() => router.push("/adicionar")}
                style={[estilos.campo, { backgroundColor: cor.fundoTela, borderColor: cor.bordaPadrao }]}
              >
                <Icone nome="buscar" cor={cor.textoSuave} />
                <Text style={[fonte("corpoPadrao"), { color: cor.textoSuave }]}>Ou busque um produto</Text>
              </Pressable>
            </View>
          )}

          {d?.atividade[0] ? (
            <View style={[estilos.atividade, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>
              <View style={[estilos.avatar, { backgroundColor: cor.marcaEtiqueta }]}>
                <Text style={[fonte("corpoForte"), { color: cor.marcaSobreEtiqueta }]}>{(d.atividade[0].quem ?? "?").charAt(0).toUpperCase()}</Text>
              </View>
              <Text style={[fonte("corpoMenor"), { color: cor.textoPrincipal, flex: 1 }]}>
                {d.atividade
                  .slice(0, 2)
                  .map((a) => `${a.quem ?? "Alguém"} ${TEXTO_DA_ATIVIDADE[a.tipo]} ${a.item} ${haQuanto(a.quando)}`)
                  .join(" · ")}
              </Text>
            </View>
          ) : null}

          {aComprar.length ? (
            <View style={estilos.acoes}>
              <View style={{ flex: 1 }}>
                <Botao
                  rotulo="Estou no mercado"
                  tipo="etiqueta"
                  largo
                  aoTocar={() => router.push({ pathname: "/no-mercado", params: comparacao.dados?.lojas[0] ? { loja: comparacao.dados.lojas[0].loja_id } : {} })}
                />
              </View>
              <Botao rotulo="Ler cupom" tipo="contorno" aoTocar={() => router.push("/ler-cupom")} />
            </View>
          ) : null}

          {doSeuMercado.length ? (
            <>
              <Titulo texto="Ofertas no seu mercado" acao="ver todas" aoTocar={() => router.navigate("/ofertas")} />
              <View style={estilos.duas}>
                {doSeuMercado.map((o) => (
                  <CartaoDeOferta
                    key={`${o.loja_id}-${o.produto.id}`}
                    oferta={o}
                    aoTocar={() => router.push({ pathname: "/produto/[id]", params: { id: o.produto.id } })}
                    aoPor={() => pôr(o.produto, false, o.produto.nome_curto ?? o.produto.nome)}
                  />
                ))}
              </View>
            </>
          ) : null}

          {d?.acabando.length ? (
            <>
              <Titulo texto="Acabando em casa?" />
              <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, marginTop: -12 }]}>A casa costuma comprar estes. Toque para pôr na lista.</Text>
              <View style={estilos.chips}>
                {d.acabando.map((a) => {
                  const rotulo = [a.nome_curto, a.tamanho_texto].filter(Boolean).join(" ");
                  return (
                    <Chip
                      key={a.produto_id}
                      texto={`+ ${rotulo}`}
                      aoTocar={() => pôr({ id: a.produto_id, nome: rotulo, marca: null, tamanho: null, unidade: null, categoria: "mercearia" }, false, rotulo)}
                    />
                  );
                })}
              </View>
            </>
          ) : null}

          {d && (d.encartes.length || d.compras_no_mes || !aComprar.length) ? (
            <>
              <Titulo texto="Nesta semana" />
              {d.encartes.map((e) => (
                <Informativo
                  key={e.rede}
                  icone="oferta"
                  titulo={`Encarte do ${e.loja.nome} · ${e.loja.distancia_km.toLocaleString("pt-BR")} km`}
                  texto={`Vale até ${new Date(`${e.valido_ate}T12:00:00`).toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit" })}. ${e.itens} ofertas, com preço de clube para quem tem o cartão.`}
                  aoTocar={() => router.navigate("/ofertas")}
                />
              ))}
              {d.compras_no_mes ? (
                <Informativo
                  icone="queda"
                  titulo={`Você economizou ${reais(d.economia_mes_centavos)} neste mês`}
                  texto={`Em ${d.compras_no_mes} ${d.compras_no_mes === 1 ? "compra" : "compras"} com o cupom lido. Leia o cupom da próxima para somar.`}
                />
              ) : null}
              {!aComprar.length ? (
                <Informativo
                  icone="familia"
                  titulo="A lista é da casa toda"
                  texto="Convide quem mora com você pelo WhatsApp: todo mundo vê e mexe na mesma lista, mesmo sem internet."
                  aoTocar={() => router.navigate("/perfil")}
                />
              ) : null}
            </>
          ) : null}

          {d?.status.conferido_em ? (
            <View style={{ alignItems: "center" }}>
              <View style={[estilos.selo, { backgroundColor: cor.fundoAfundado }]}>
                <Text style={[fonte("seloDeFonte"), { color: cor.textoSuave }]}>
                  {`${seloDeFonte("conferido", d.status.conferido_em)} · ${d.status.redes} REDES · ${d.status.produtos} PRODUTOS`}
                </Text>
              </View>
            </View>
          ) : inicio.carregando && !d ? (
            <ActivityIndicator color={cor.estadoEconomia} />
          ) : null}
        </>
      )}

      <SeletorDeBairro
        visivel={escolhendoBairro}
        selecionado={sessao?.bairro_id ?? null}
        aoFechar={() => setEscolhendoBairro(false)}
        aoConfirmar={(b) => {
          setEscolhendoBairro(false);
          trocarBairro(b).catch(() => Alert.alert("Sem internet", "Não deu para trocar o bairro agora. Tente de novo em instantes."));
        }}
      />
    </ScrollView>
  );
}

/** A lista no mercado recomendado, com o porquê (R8: só outro mercado quando a viagem compensa). */
function CartaoDaLista({ comparacao, itens, carregando, semConexao }: { comparacao: Comparacao | null; itens: number; carregando: boolean; semConexao: boolean }) {
  const { cor } = useTema();
  const lojas = comparacao?.lojas ?? [];
  const rec = lojas[0];
  if (!rec) {
    return (
      <View style={[estilos.cartaoGrande, { backgroundColor: cor.fundoSuperficie, borderWidth: 1, borderColor: cor.bordaPadrao, flexDirection: "row", alignItems: "center" }]}>
        {carregando ? <ActivityIndicator color={cor.estadoEconomia} /> : null}
        <Text style={[fonte("corpoMenor"), { color: cor.textoSuave, flex: 1 }]}>
          {semConexao ? "Sem internet: a comparação aparece quando a conexão voltar." : "Calculando quanto fica a sua lista…"}
        </Text>
      </View>
    );
  }
  const barata = lojas.reduce((a, b) => (b.total_centavos < a.total_centavos ? b : a), rec);
  let porque: string;
  if (barata.loja_id !== rec.loja_id) {
    const viagem = Math.max(0, barata.custo_viagem_centavos - rec.custo_viagem_centavos);
    porque = `No ${barata.rede} sai ${reais(rec.total_centavos - barata.total_centavos)} mais barato, mas a ida e volta a mais custa cerca de ${reais(viagem)}. Aqui sai melhor.`;
  } else if (lojas.length > 1) {
    const segunda = [...lojas].sort((a, b) => a.total_centavos - b.total_centavos)[1]!;
    porque = `É o mais barato hoje: ${reais(segunda.total_centavos - rec.total_centavos)} a menos que no ${segunda.rede}.`;
  } else porque = "Só este mercado tem preço de todos os itens por enquanto.";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Sua lista, ${itens} itens: ${reais(rec.total_centavos)} no ${rec.nome}. ${porque} Comparar`}
      onPress={() => router.navigate("/comparar")}
      style={[estilos.cartaoGrande, { backgroundColor: cor.fundoProfundo }]}
    >
      <Text style={[fonte("rotulo"), { color: cor.textoInverso, opacity: 0.75 }]}>SUA LISTA · {itens} {itens === 1 ? "ITEM" : "ITENS"}</Text>
      <View style={estilos.linhaPreco}>
        <Text style={[fonte("precoGrande"), { color: cor.textoInverso }]}>{reais(rec.total_centavos)}</Text>
        <View style={[estilos.etiqueta, { backgroundColor: cor.marcaEtiqueta }]}>
          <Text style={[fonte("rotulo"), { color: cor.marcaSobreEtiqueta }]}>{barata.loja_id === rec.loja_id ? "MAIS BARATO" : "MELHOR PARA VOCÊ"}</Text>
        </View>
      </View>
      <Text style={[fonte("corpoPadrao"), { color: cor.textoInverso }]}>
        no {rec.nome}
        {rec.seu_mercado ? ", o seu mercado" : ""}
      </Text>
      <View style={[estilos.divisor, { backgroundColor: cor.sobreposicaoDivisor }]} />
      <Text style={[fonte("corpoMenor"), { color: cor.textoInverso, opacity: 0.85 }]}>{porque}</Text>
      <View style={estilos.rodape}>
        {rec.preco_mais_antigo_em ? (
          <View style={[estilos.selo, { backgroundColor: cor.sobreposicaoVidro }]}>
            <Text style={[fonte("seloDeFonte"), { color: cor.textoInverso }]}>{seloDeFonte("preços", rec.preco_mais_antigo_em)}</Text>
          </View>
        ) : null}
        <View style={{ flex: 1 }} />
        <Text style={[fonte("corpoForte"), { color: cor.marcaEtiqueta }]}>Comparar ›</Text>
      </View>
    </Pressable>
  );
}

function Titulo({ texto, acao, aoTocar }: { texto: string; acao?: string; aoTocar?: () => void }) {
  const { cor } = useTema();
  return (
    <View style={estilos.titulo}>
      <Text accessibilityRole="header" style={[fonte("tituloSecao"), { color: cor.textoPrincipal, flex: 1 }]}>
        {texto}
      </Text>
      {acao ? (
        <Text accessibilityRole="button" onPress={aoTocar} style={[fonte("corpoMenor"), { color: cor.estadoEconomia }]}>
          {acao}
        </Text>
      ) : null}
    </View>
  );
}

function Informativo({ icone, titulo, texto, aoTocar }: { icone: NomeIcone; titulo: string; texto: string; aoTocar?: () => void }) {
  const { cor } = useTema();
  return (
    <Pressable
      accessibilityRole={aoTocar ? "button" : undefined}
      disabled={!aoTocar}
      onPress={aoTocar}
      style={[estilos.informativo, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}
    >
      <View style={[estilos.iconeRedondo, { backgroundColor: cor.estadoEconomiaSuave }]}>
        <Icone nome={icone} cor={cor.estadoEconomia} tamanho={20} />
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{titulo}</Text>
        <Text style={[fonte("corpoMenor"), { color: cor.textoSuave }]}>{texto}</Text>
      </View>
    </Pressable>
  );
}

const estilos = StyleSheet.create({
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 20 },
  cabecalho: { flexDirection: "row", alignItems: "center", gap: 12, paddingTop: 4 },
  bairro: { flexDirection: "row", alignItems: "center", gap: 4, minHeight: 36, alignSelf: "flex-start" },
  casa: { flexDirection: "row" },
  membro: { width: 44, height: 44, borderRadius: 22, borderWidth: 2.5, alignItems: "center", justifyContent: "center" },
  cartaoGrande: { borderRadius: 28, padding: 20, gap: 12 },
  linhaPreco: { flexDirection: "row", alignItems: "center", gap: 12, flexWrap: "wrap" },
  etiqueta: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  divisor: { height: 1 },
  rodape: { flexDirection: "row", alignItems: "center", gap: 8 },
  selo: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  campo: { flexDirection: "row", alignItems: "center", gap: 12, height: 54, borderRadius: 27, borderWidth: 1, paddingHorizontal: 16 },
  atividade: { flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: 14, borderWidth: 1, marginTop: -8 },
  avatar: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  acoes: { flexDirection: "row", gap: 12 },
  duas: { flexDirection: "row", gap: 14 },
  titulo: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: -8 },
  informativo: { flexDirection: "row", gap: 12, padding: 16, borderRadius: 20, borderWidth: 1 },
  iconeRedondo: { width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center" },
});
