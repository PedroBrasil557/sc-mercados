/** 11 Perfil: a casa, o bairro, os dados. */
import { router } from "expo-router";
import { type ReactNode, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Botao } from "@/componentes/Botao";
import { ChaveDoAviso, ExplicacaoDosAvisos, useAvisoDeQuinta } from "@/componentes/AvisoDeQuinta";
import { Campo } from "@/componentes/Campo";
import { ConvidarCasa } from "@/componentes/ConvidarCasa";
import { Icone, type NomeIcone } from "@/componentes/Icone";
import { PainelRecuperacao } from "@/componentes/PainelRecuperacao";
import { PainelInferior } from "@/componentes/PainelInferior";
import { SeletorDeBairro } from "@/componentes/SeletorDeBairro";
import { custoKm, definirCustoKm, lojasPreferidas, OPCOES_DE_VIAGEM, useComparacao } from "@/lista/comparacao";
import { trocarApelido, trocarBairro, useLista } from "@/lista/sincronia";
import { fonte, useTema } from "@/tema";

export default function Perfil() {
  const { cor } = useTema();
  const margem = useSafeAreaInsets();
  const { sessao } = useLista();
  const [convidando, setConvidando] = useState(false);
  const [escolhendoBairro, setEscolhendoBairro] = useState(false);
  const [renomeando, setRenomeando] = useState(false);
  const [recuperando, setRecuperando] = useState(false);
  const [escolhendoViagem, setEscolhendoViagem] = useState(false);
  const aviso = useAvisoDeQuinta();
  const { dados } = useComparacao();
  if (!sessao) return null;
  const preferidas = Object.values(lojasPreferidas());
  const favoritas = (dados?.lojas ?? []).filter((l) => preferidas.includes(l.loja_id)).map((l) => l.nome);
  const viagem = OPCOES_DE_VIAGEM.find((o) => o.centavos === custoKm()) ?? OPCOES_DE_VIAGEM[0];
  const outros = Object.entries(sessao.nomes).filter(([id]) => id !== sessao.membro_id);

  return (
    <ScrollView style={{ backgroundColor: cor.fundoTela }} contentContainerStyle={[estilos.conteudo, { paddingTop: margem.top + 4 }]}>
      <Text accessibilityRole="header" style={[fonte("tituloTela"), { color: cor.textoPrincipal }]}>
        Perfil
      </Text>

      <Grupo>
        <Linha
          avatar={{ letra: sessao.apelido.charAt(0), destaque: true }}
          titulo={sessao.apelido === "Eu" ? "Você" : `${sessao.apelido} (você)`}
          detalhe="Toque para mudar o seu nome"
          aoTocar={() => setRenomeando(true)}
        />
        {outros.map(([id, nome]) => (
          <Linha key={id} avatar={{ letra: nome.charAt(0) }} titulo={nome} detalhe="Participa da lista da casa" />
        ))}
        <Linha icone="mais" titulo="Convidar alguém da casa" detalhe="Pelo WhatsApp, com um código" aoTocar={() => setConvidando(true)} ultima />
      </Grupo>

      <Grupo>
        <Linha
          icone="local"
          titulo={sessao.bairro_nome ?? "Escolher o bairro"}
          detalhe="Usamos só o bairro, nunca sua localização"
          aoTocar={() => setEscolhendoBairro(true)}
        />
        <Linha
          icone="loja"
          titulo="Lojas favoritas"
          detalhe={favoritas.length ? favoritas.join(", ") : "A mais perto de cada rede. Para trocar, toque num mercado em Comparar"}
          aoTocar={() => router.navigate("/comparar")}
        />
        <Linha
          icone="rota"
          titulo={`Custo da viagem: ${viagem.nome.toLowerCase()}`}
          detalhe="Conta na hora de dizer se vale ir a um mercado mais longe"
          aoTocar={() => setEscolhendoViagem(true)}
          ultima
        />
      </Grupo>

      <Grupo>
        <Linha icone="aviso" titulo="Ofertas de quinta-feira" detalhe="1 aviso por semana" direita={<ChaveDoAviso ligado={aviso.ligado} aoMudar={(v) => void aviso.alternar(v)} semRotulo />} />
        <Linha icone="oferta" titulo="Preço de sócio dos clubes" detalhe="Clube Mais, cooperado, Amigo Giassi" selo="Em breve" ultima />
      </Grupo>

      <Grupo>
        <Linha icone="historico" titulo="Não perca a sua lista" detalhe="Código para usar num celular novo" aoTocar={() => setRecuperando(true)} />
        <Linha icone="info" titulo="Seus dados" detalhe="Não guardamos CPF nem localização" aoTocar={() => router.push("/dados")} ultima />
      </Grupo>

      <ConvidarCasa visivel={convidando} aoFechar={() => setConvidando(false)} />
      <PainelRecuperacao visivel={recuperando} aoFechar={() => setRecuperando(false)} />
      <PainelInferior visivel={escolhendoViagem} titulo="Como você vai ao mercado?" aoFechar={() => setEscolhendoViagem(false)}>
        {OPCOES_DE_VIAGEM.map((o) => (
          <Linha
            key={o.nome}
            icone={o.centavos === viagem.centavos ? "ok" : "rota"}
            titulo={o.nome}
            detalhe={o.detalhe}
            aoTocar={() => {
              definirCustoKm(o.centavos);
              setEscolhendoViagem(false);
            }}
          />
        ))}
      </PainelInferior>
      <ExplicacaoDosAvisos visivel={aviso.explicando} aoPermitir={() => void aviso.ligar()} aoFechar={aviso.fecharExplicacao} />
      <SeletorDeBairro
        visivel={escolhendoBairro}
        selecionado={sessao.bairro_id ?? null}
        aoFechar={() => setEscolhendoBairro(false)}
        aoConfirmar={(b) => {
          setEscolhendoBairro(false);
          trocarBairro(b).catch(() => Alert.alert("Sem internet", "Não deu para trocar o bairro agora."));
        }}
      />
      <Renomear visivel={renomeando} atual={sessao.apelido === "Eu" ? "" : sessao.apelido} aoFechar={() => setRenomeando(false)} />
    </ScrollView>
  );
}

function Grupo({ children }: { children: ReactNode }) {
  const { cor } = useTema();
  return <View style={[estilos.grupo, { backgroundColor: cor.fundoSuperficie, borderColor: cor.bordaPadrao }]}>{children}</View>;
}

type LinhaProps = {
  titulo: string;
  detalhe: string;
  icone?: NomeIcone;
  avatar?: { letra: string; destaque?: boolean };
  selo?: string;
  direita?: ReactNode;
  aoTocar?: () => void;
  ultima?: boolean;
};

function Linha({ titulo, detalhe, icone, avatar, selo, direita, aoTocar, ultima }: LinhaProps) {
  const { cor } = useTema();
  const conteudo = (
    <>
      {avatar ? (
        <View style={[estilos.circulo, { backgroundColor: avatar.destaque ? cor.marcaEtiqueta : cor.estadoEconomiaSuave }]}>
          <Text style={[fonte("corpoForte"), { color: avatar.destaque ? cor.marcaSobreEtiqueta : cor.textoPrincipal }]}>{avatar.letra.toUpperCase()}</Text>
        </View>
      ) : icone ? (
        <View style={[estilos.circulo, { backgroundColor: cor.fundoAfundado }]}>
          <Icone nome={icone} cor={cor.textoPrincipal} tamanho={20} />
        </View>
      ) : null}
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[fonte("corpoForte"), { color: cor.textoPrincipal }]}>{titulo}</Text>
        <Text style={[fonte("legenda"), { color: cor.textoSuave }]}>{detalhe}</Text>
      </View>
      {direita ? (
        direita
      ) : selo ? (
        <View style={[estilos.selo, { backgroundColor: cor.fundoAfundado }]}>
          <Text style={[fonte("rotulo"), { color: cor.textoSuave }]}>{selo}</Text>
        </View>
      ) : aoTocar ? (
        <Icone nome="seta-direita" cor={cor.textoSuave} tamanho={20} />
      ) : null}
    </>
  );
  const estilo = [estilos.linha, !ultima && { borderBottomWidth: 1, borderBottomColor: cor.bordaPadrao }];
  return aoTocar ? (
    <Pressable accessibilityRole="button" accessibilityLabel={`${titulo}. ${detalhe}`} onPress={aoTocar} style={estilo}>
      {conteudo}
    </Pressable>
  ) : (
    <View accessible accessibilityLabel={`${titulo}. ${detalhe}${selo ? `. ${selo}` : ""}`} style={estilo}>
      {conteudo}
    </View>
  );
}

function Renomear({ visivel, atual, aoFechar }: { visivel: boolean; atual: string; aoFechar: () => void }) {
  const { cor, medida } = useTema();
  const [nome, setNome] = useState(atual);
  const [ocupado, setOcupado] = useState(false);
  return (
    <Modal visible={visivel} transparent animationType="fade" onRequestClose={aoFechar} onShow={() => setNome(atual)}>
      <View style={[estilos.centro, { backgroundColor: cor.sobreposicaoVeu }]}>
        <View style={[estilos.dialogo, { backgroundColor: cor.fundoSuperficie, borderRadius: medida.raioGrande }]}>
          <Text style={[fonte("tituloSecao"), { color: cor.textoPrincipal }]}>Como a família te chama?</Text>
          <Campo rotulo="Seu nome" autoFocus value={nome} onChangeText={setNome} maxLength={40} />
          <Botao
            rotulo="Salvar"
            largo
            ocupado={ocupado}
            desativado={!nome.trim()}
            aoTocar={() => {
              setOcupado(true);
              trocarApelido(nome)
                .then(aoFechar)
                .catch(() => Alert.alert("Sem internet", "Não deu para salvar o nome agora."))
                .finally(() => setOcupado(false));
            }}
          />
          <Botao rotulo="Cancelar" tipo="contorno" largo aoTocar={aoFechar} />
        </View>
      </View>
    </Modal>
  );
}

const estilos = StyleSheet.create({
  conteudo: { paddingHorizontal: 20, paddingBottom: 32, gap: 16 },
  grupo: { borderRadius: 20, borderWidth: 1, overflow: "hidden" },
  linha: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 64, paddingHorizontal: 16, paddingVertical: 12 },
  circulo: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  selo: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  centro: { flex: 1, justifyContent: "center", padding: 24 },
  dialogo: { padding: 24, gap: 16 },
});
