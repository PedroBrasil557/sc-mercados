"""Itens vendidos por quilo (fase 1): genéricos básicos com o preço do quilo em cada loja.

Pão francês, banana e patinho não têm código de barras comum entre as redes: cada uma usa um código interno.
Por isso o item por quilo de cada rede é ligado a um GENÉRICO nosso pelo nome, com regra estrita:
- o nome, sem a marca e sem as palavras que não mudam o produto (kg, resfriado, bandeja...), precisa ter TODAS as
  palavras do genérico e NENHUMA outra além das que ele aceita. "Pão Francês Crocante" não é "Pão francês";
  "Patinho Bovino Moído" não é "Patinho em pedaço"; "Banana Orgânica" não é "Banana". Na dúvida, não liga
  (regra do projeto: não misturar produtos entre mercados);
- a marca não importa: o genérico é "qualquer marca", e cada loja entra com o mais barato dos que casam;
- nome com peso fixo ("180g", "1kg") é embalagem, não item por quilo: fica de fora.
O preço gravado é o do quilo. Fase 1: aparece na busca e no produto; ainda não entra no total da lista.
"""

import re
import unicodedata
import uuid
from dataclasses import dataclass

# Os genéricos são produtos do catálogo de 1 kg (tamanho 1000 g), marcados em atributos.por_kg.
ESPACO_UUID = uuid.UUID("5b0a4c1e-7d0f-4f7e-9a51-2f6a0c3b8e11")


@dataclass(frozen=True)
class Generico:
    slug: str
    nome: str
    categoria: str
    exige: frozenset[str]
    aceita: frozenset[str]

    @property
    def produto_id(self) -> str:
        return str(uuid.uuid5(ESPACO_UUID, self.slug))


def _g(slug: str, nome: str, categoria: str, exige: str, aceita: str = "") -> Generico:
    return Generico(slug, nome, categoria, frozenset(exige.split()), frozenset(aceita.split()))


_BOV = "carne bovino pedaco sem_osso"
_SUI = "suino pedaco congelado"
_FRA = "frango congelado"

GENERICOS: list[Generico] = [
    # ---- padaria ----
    _g("pao-frances", "Pão francês", "padaria", "pao frances"),
    # ---- hortifrúti ----
    _g("banana-caturra", "Banana caturra", "hortifruti", "banana caturra"),
    _g("banana-prata", "Banana prata", "hortifruti", "banana prata"),
    _g("banana-branca", "Banana branca", "hortifruti", "banana branco"),
    _g("banana-maca", "Banana maçã", "hortifruti", "banana maca"),
    _g("banana-da-terra", "Banana-da-terra", "hortifruti", "banana terra"),
    _g("maca-gala", "Maçã gala", "hortifruti", "maca gala"),
    _g("maca-fuji", "Maçã fuji", "hortifruti", "maca fuji"),
    _g("laranja-pera", "Laranja pera", "hortifruti", "laranja pera"),
    _g("laranja-lima", "Laranja lima", "hortifruti", "laranja lima"),
    _g("bergamota", "Bergamota", "hortifruti", "bergamota", "laranja"),
    _g("limao-taiti", "Limão taiti", "hortifruti", "limao taiti"),
    _g("tomate", "Tomate", "hortifruti", "tomate", "longa vida"),
    _g("tomate-italiano", "Tomate italiano", "hortifruti", "tomate italiano"),
    _g("batata", "Batata inglesa", "hortifruti", "batata", "lavado"),
    _g("batata-doce", "Batata-doce", "hortifruti", "batatadoce"),
    _g("batata-salsa", "Batata-salsa (mandioquinha)", "hortifruti", "batatasalsa"),
    _g("cebola", "Cebola", "hortifruti", "cebola", "branco"),
    _g("cebola-roxa", "Cebola roxa", "hortifruti", "cebola roxo"),
    _g("alho", "Alho", "hortifruti", "alho"),
    _g("cenoura", "Cenoura", "hortifruti", "cenoura"),
    _g("beterraba", "Beterraba", "hortifruti", "beterraba"),
    _g("chuchu", "Chuchu", "hortifruti", "chuchu"),
    _g("abobrinha-italiana", "Abobrinha italiana", "hortifruti", "abobrinha italiano"),
    _g("pepino", "Pepino", "hortifruti", "pepino"),
    _g("pimentao-verde", "Pimentão verde", "hortifruti", "pimentao verde"),
    _g("aipim", "Aipim", "hortifruti", "aipim", "com_casca"),
    _g("abobora-cabotia", "Abóbora cabotiá", "hortifruti", "abobora cabotia"),
    _g("mamao-formosa", "Mamão formosa", "hortifruti", "mamao formosa"),
    _g("mamao-papaya", "Mamão papaya", "hortifruti", "mamao papaya"),
    _g("melancia", "Melancia", "hortifruti", "melancia", "inteiro"),
    _g("melao-amarelo", "Melão amarelo", "hortifruti", "melao amarelo"),
    _g("manga-palmer", "Manga palmer", "hortifruti", "manga palmer"),
    _g("manga-tommy", "Manga tommy", "hortifruti", "manga tommy"),
    _g("abacate", "Abacate", "hortifruti", "abacate"),
    _g("gengibre", "Gengibre", "hortifruti", "gengibre"),
    _g("repolho", "Repolho verde", "hortifruti", "repolho", "verde"),
    # ---- carne bovina ----
    _g("carne-moida", "Carne moída bovina", "carnes", "carne moido", "bovino"),
    _g("patinho", "Patinho em pedaço", "carnes", "patinho", _BOV),
    _g("patinho-moido", "Patinho moído", "carnes", "patinho moido", "carne bovino sem_osso"),
    _g("patinho-bife", "Patinho em bife", "carnes", "patinho bife", "carne bovino sem_osso"),
    _g("coxao-mole", "Coxão mole em pedaço", "carnes", "coxao mole", _BOV),
    _g("coxao-mole-bife", "Coxão mole em bife", "carnes", "coxao mole bife", "carne bovino sem_osso"),
    _g("coxao-mole-moido", "Coxão mole moído", "carnes", "coxao mole moido", "carne bovino sem_osso"),
    _g("coxao-duro", "Coxão duro em pedaço", "carnes", "coxao duro", _BOV),
    _g("coxao-duro-moido", "Coxão duro moído", "carnes", "coxao duro moido", "carne bovino sem_osso"),
    _g("acem", "Acém em pedaço", "carnes", "acem", _BOV),
    _g("acem-moido", "Acém moído", "carnes", "acem moido", "carne bovino sem_osso"),
    _g("alcatra", "Alcatra em pedaço", "carnes", "alcatra", _BOV),
    _g("alcatra-bife", "Alcatra em bife", "carnes", "alcatra bife", "carne bovino sem_osso"),
    _g("alcatra-com-maminha", "Alcatra com maminha em pedaço", "carnes", "alcatra com_maminha", _BOV),
    _g("contrafile", "Contrafilé em pedaço", "carnes", "contrafile", _BOV),
    _g("contrafile-bife", "Contrafilé em bife", "carnes", "contrafile bife", "carne bovino sem_osso"),
    _g("picanha", "Picanha", "carnes", "picanha", _BOV),
    _g("maminha", "Maminha", "carnes", "maminha", _BOV + " alcatra"),
    _g("fraldinha", "Fraldinha", "carnes", "fraldinha", _BOV),
    _g("file-mignon", "Filé-mignon", "carnes", "filemignon", _BOV),
    _g("musculo", "Músculo em pedaço", "carnes", "musculo", _BOV),
    _g("paleta-bovina", "Paleta bovina em pedaço", "carnes", "paleta bovino", "carne pedaco sem_osso"),
    _g("cupim", "Cupim", "carnes", "cupim", _BOV),
    _g("costela-bovina", "Costela bovina", "carnes", "costela bovino", "carne pedaco com_osso"),
    _g("figado-bovino", "Fígado bovino", "carnes", "figado bovino", "carne"),
    # ---- carne suína ----
    _g("bisteca-suina", "Bisteca suína", "carnes", "bisteca suino", "congelado fatiado"),
    _g("costela-suina", "Costela suína", "carnes", "costela suino", _SUI + " com_osso"),
    _g("lombo-suino", "Lombo suíno", "carnes", "lombo suino", _SUI + " sem_osso"),
    _g("pernil-suino", "Pernil suíno", "carnes", "pernil suino", _SUI),
    _g("panceta", "Panceta suína", "carnes", "panceta suino", "congelado"),
    _g("linguica-toscana", "Linguiça toscana", "carnes", "linguica toscana", "suino congelado"),
    _g("linguica-calabresa", "Linguiça calabresa", "carnes", "linguica calabresa", "defumado"),
    _g("linguica-blumenau", "Linguiça Blumenau", "carnes", "linguica blumenau"),
    _g("bacon-pedaco", "Bacon em pedaço", "carnes", "bacon", "defumado pedaco"),
    _g("bacon-fatiado", "Bacon fatiado", "carnes", "bacon fatiado", "defumado"),
    # ---- frango ----
    _g("frango-inteiro", "Frango inteiro", "carnes", "frango inteiro", "congelado com_miudos"),
    _g("peito-frango", "Peito de frango com osso", "carnes", "peito frango", _FRA + " com_osso"),
    _g("file-peito-frango", "Filé de peito de frango", "carnes", "filepeito frango", _FRA + " pedaco"),
    _g("coxa-sobrecoxa", "Coxa e sobrecoxa de frango", "carnes", "coxasobrecoxa frango", _FRA + " sem_dorso"),
    _g("coxa-frango", "Coxa de frango", "carnes", "coxa frango", _FRA),
    _g("sobrecoxa-frango", "Sobrecoxa de frango", "carnes", "sobrecoxa frango", _FRA),
    _g("asa-frango", "Asa de frango", "carnes", "asa frango", _FRA),
    _g("coracao-frango", "Coração de frango", "carnes", "coracao frango", _FRA),
    _g("moela-frango", "Moela de frango", "carnes", "moela frango", _FRA),
    _g("figado-frango", "Fígado de frango", "carnes", "figado frango", _FRA),
    # ---- frios e queijos ----
    _g("presunto-fatiado", "Presunto fatiado", "laticinios", "presunto fatiado", "cozido sem_capa gordura"),
    _g("apresuntado-fatiado", "Apresuntado fatiado", "laticinios", "apresuntado fatiado"),
    _g("mortadela-fatiada", "Mortadela fatiada", "laticinios", "mortadela fatiado"),
    _g("mortadela", "Mortadela em pedaço", "laticinios", "mortadela", "pedaco"),
    _g("mussarela-fatiada", "Queijo mussarela fatiado", "laticinios", "queijo mussarela fatiado"),
    _g("mussarela", "Queijo mussarela em pedaço", "laticinios", "queijo mussarela", "pedaco lanche"),
    _g("prato-fatiado", "Queijo prato fatiado", "laticinios", "queijo prato fatiado"),
    _g("prato", "Queijo prato em pedaço", "laticinios", "queijo prato", "pedaco lanche"),
    _g("minas-frescal", "Queijo minas frescal", "laticinios", "queijo minas frescal"),
    _g("minas-padrao", "Queijo minas padrão", "laticinios", "queijo minas padrao", "pedaco"),
    _g("queijo-colonial", "Queijo colonial", "laticinios", "queijo colonial", "pedaco"),
    _g("parmesao", "Queijo parmesão", "laticinios", "queijo parmesao", "pedaco cunha"),
    _g("ricota", "Ricota", "laticinios", "ricota", "fresco com_sal"),
    _g("salame-italiano", "Salame tipo italiano", "laticinios", "salame italiano", "tipo"),
    _g("peito-peru-fatiado", "Peito de peru fatiado", "laticinios", "peitoperu fatiado", "defumado cozido"),
]
POR_SLUG = {g.slug: g for g in GENERICOS}
POR_PRODUTO = {g.produto_id: g for g in GENERICOS}

# ---------- leitura do nome ----------

# Marcas e produtores vistos nos itens por quilo das redes (o campo "marca" do site nem sempre traz a do nome).
MARCAS = sorted(
    {
        "agrolife",
        "amanhecer",
        "angelo scussel",
        "angeloni",
        "atilatte",
        "aurora",
        "ave serra",
        "baldo",
        "bassi",
        "becker",
        "best beef",
        "big frios",
        "bom destino",
        "borrussia",
        "bridor",
        "buchner",
        "calemba",
        "cancao",
        "cantu oeste",
        "cantu",
        "carneiro sul",
        "celso e sucharski",
        "ceratti",
        "chef foods",
        "conaprole",
        "cooper",
        "copacol",
        "crioulo",
        "cruzilia",
        "d farm",
        "d'farm",
        "della vita",
        "di baldo",
        "dipaes",
        "disner",
        "do sitio",
        "dom bruno",
        "d talia",
        "dtalia",
        "d'talia",
        "duvalle",
        "el maestro",
        "estancia gaucha",
        "excelsior",
        "famiglia baldo",
        "fazenda velha",
        "ferreira",
        "fragnani",
        "friboi",
        "fricar",
        "frigosul",
        "frimazo",
        "frimesa",
        "gessner",
        "gesnner",
        "giassi",
        "gran formaggio",
        "gran mestri",
        "guinther",
        "holandes",
        "hortifruti",
        "irmaos novaes",
        "komdelli",
        "la paulina",
        "lar",
        "lasaroli",
        "lucelmar",
        "macedo",
        "maroca",
        "marquespan",
        "massotti",
        "maturatta",
        "montana",
        "morgana",
        "morro azul",
        "nacon",
        "nho bento",
        "nobre",
        "pamplona",
        "papenborg",
        "perdigao",
        "perola",
        "pingo doce",
        "polenghi",
        "polico",
        "polzin",
        "pomerode",
        "possamai",
        "president",
        "pul",
        "quata",
        "renkawiecki",
        "sadia",
        "sao joao",
        "sao joaquim",
        "sao pedro",
        "sao vicente",
        "schmitz",
        "seara",
        "silvestrin",
        "slf",
        "sr pao",
        "sr.pao",
        "sulbeef",
        "sulfrios",
        "sulita",
        "superpan",
        "tirol",
        "tirolez",
        "top quality",
        "tradicao",
        "veneza",
        "verde campo",
        "verdi",
        "vida nova",
        "vigor",
        "villa germania",
        "central de carnes",
        "central de carnes cooper",
    },
    key=len,
    reverse=True,  # a mais longa primeiro: "central de carnes cooper" antes de "cooper"
)
_MARCAS_RE = re.compile(r"\b(" + "|".join(re.escape(m) for m in MARCAS) + r")\b")

# Peso fixo no nome: é embalagem, não item por quilo.
_PESO_FIXO = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:g|gr|grs|ml|l|kg)\b")

_FRASES = [
    (re.compile(r"\(inteir[oa] ou fatiad[oa]\)"), " "),
    (re.compile(r"\bcontra[\s-]?file\b"), "contrafile"),
    (re.compile(r"\bfile[\s-]mignon\b"), "filemignon"),
    (re.compile(r"\bcoxas? (?:e |com )?sobrecoxas?\b"), "coxasobrecoxa"),
    (re.compile(r"\bpeito de peru\b"), "peitoperu"),
    (re.compile(r"\bfile de peito\b"), "filepeito"),
    (re.compile(r"\bbatata[\s-]doce\b"), "batatadoce"),
    (re.compile(r"\bbatata salsa\b|\bmandioquinha\b"), "batatasalsa"),
    (re.compile(r"\bbatata inglesa\b"), "batata"),
    (re.compile(r"\bbanana da terra\b"), "banana terra"),
    (re.compile(r"\bmandioca\b"), "aipim"),
    (re.compile(r"\b(?:mu[cç]arela|mozzarella|mozarela|mussarella)\b"), "mussarela"),
    (re.compile(r"\btahiti\b"), "taiti"),
    (re.compile(r"\b(sem|com) (\w+)"), r"\1_\2"),
]

_SINONIMOS = {
    "bovina": "bovino",
    "suina": "suino",
    "resfriada": "resfriado",
    "resfriados": "resfriado",
    "congelada": "congelado",
    "congelados": "congelado",
    "moida": "moido",
    "fatiada": "fatiado",
    "fatias": "fatiado",
    "fatiados": "fatiado",
    "defumada": "defumado",
    "temperada": "temperado",
    "temperados": "temperado",
    "pedacos": "pedaco",
    "peca": "pedaco",
    "fracionado": "pedaco",
    "fracionada": "pedaco",
    "fracao": "pedaco",
    "bifes": "bife",
    "inteira": "inteiro",
    "organica": "organico",
    "branca": "branco",
    "roxa": "roxo",
    "lavada": "lavado",
    "italiana": "italiano",
    "coxas": "coxa",
    "sobrecoxas": "sobrecoxa",
    "asas": "asa",
    "fresca": "fresco",
    "cozida": "cozido",
    "bananas": "banana",
    "cabotian": "cabotia",
    "cabotiã": "cabotia",
}

# Palavras que não mudam o produto: unidade, conservação comum, embalagem, ligação.
NEUTRAS = frozenset(
    "kg granel resfriado vacuo bandeja bandejas pacote nacional comum tradicional aprox aproximadamente "
    "sem_tempero de da do das dos em a e o na no ao para".split()
)


def _simples(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def palavras(nome: str, marca: str | None = None) -> frozenset[str] | None:
    """As palavras que dizem o que o item é, sem marca nem palavras neutras. None: tem peso fixo no nome."""
    t = _simples(nome)
    if _PESO_FIXO.search(t):
        return None
    if marca:
        m = _simples(marca).strip()
        if m:
            t = re.sub(r"\b" + re.escape(m) + r"\b", " ", t)
    t = _MARCAS_RE.sub(" ", t)
    t = re.sub(r"[^a-z0-9_'\s]", " ", t).replace("'", " ")
    for padrao, troca in _FRASES:
        t = padrao.sub(troca, t)
    saida = set()
    for w in t.split():
        w = _SINONIMOS.get(w, w)
        if w not in NEUTRAS:
            saida.add(w)
    return frozenset(saida)


def generico_do_item(nome: str, marca: str | None = None) -> Generico | None:
    """O genérico deste item por quilo, só quando exatamente um casa; senão None."""
    p = palavras(nome, marca)
    if not p:
        return None
    casam = [g for g in GENERICOS if g.exige <= p and p - g.exige <= g.aceita]
    return casam[0] if len(casam) == 1 else None
