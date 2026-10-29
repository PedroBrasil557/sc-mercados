"""Leitura de tamanho e de embalagem múltipla a partir do nome do produto (R1, R2)."""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Tamanho:
    quantidade: float  # em g, ml ou unidades
    unidade: str  # "g", "ml" ou "un"

    def mesmo_que(self, outro: "Tamanho", tolerancia: float = 0.0) -> bool:
        if self.unidade != outro.unidade:
            return False
        maior = max(self.quantidade, outro.quantidade)
        return abs(self.quantidade - outro.quantidade) <= maior * tolerancia + 1e-9


_UNIDADES = {
    "kg": ("g", 1000),
    "g": ("g", 1),
    "l": ("ml", 1000),
    "litro": ("ml", 1000),
    "litros": ("ml", 1000),
    "ml": ("ml", 1),
    "un": ("un", 1),
    "unidades": ("un", 1),
    "rolos": ("un", 1),
}
_RE_TAMANHO = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|litros?|un|unidades|rolos)\b")
_RE_MULTIPLA = re.compile(r"\b(?:(?:pack|kit|fardo)\b|leve \d+ pague|\d+\s*x\s*\d)")
_MARCAS_COM_KIT = re.compile(r"\bkit\s?kat\b")  # chocolate, não kit


def _simplificar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return texto.lower().replace("\u00a0", " ")


def extrair(nome: str) -> Tamanho | None:
    """Primeiro tamanho do nome, convertido para g, ml ou unidades."""
    achado = _RE_TAMANHO.search(_simplificar(nome))
    if not achado:
        return None
    valor = float(achado.group(1).replace(",", "."))
    unidade, fator = _UNIDADES[achado.group(2)]
    return Tamanho(round(valor * fator, 3), unidade)


def todos(nome: str) -> list[Tamanho]:
    """Todos os tamanhos do nome ("Nescau Protein 15g de Proteínas 250ml" -> 15 g e 250 ml)."""
    saida = []
    for valor, sufixo in _RE_TAMANHO.findall(_simplificar(nome)):
        unidade, fator = _UNIDADES[sufixo]
        saida.append(Tamanho(round(float(valor.replace(",", ".")) * fator, 3), unidade))
    return saida


def mesmo_tamanho_no_site(nome_no_site: str, quantidade, unidade: str | None) -> bool:
    """O nome no site da rede é do mesmo produto do catálogo? (R1: o mesmo código de barras às vezes é usado
    para outra embalagem: o display com 20 chocolates, a embalagem que mudou de 150 g para 200 g.)

    Falso com pacote de vários ou quando nenhum tamanho do nome bate com o do produto (2% de folga).
    Sem tamanho legível no nome, aceita: não há prova de que é outro.
    """
    if embalagem_multipla(nome_no_site):
        return False
    if quantidade is None or unidade is None:
        return True
    alvo = Tamanho(float(quantidade), unidade)
    mesma_unidade = [t for t in todos(nome_no_site) if t.unidade == unidade]
    return not mesma_unidade or any(t.mesmo_que(alvo, 0.02) for t in mesma_unidade)


def embalagem_multipla(nome: str) -> bool:
    """Pack, kit, fardo, "leve X pague Y", "N x 500 g" ou "N unidades de 120 g cada".

    "Com 30 unidades" sozinho não é pacote de vários: ovos com 30, filtro com 30 e fralda com 58 são o
    próprio produto (coleta de 29/10/2026). Pacote de vários diz o tamanho de cada um.
    """
    texto = _MARCAS_COM_KIT.sub(" ", _simplificar(nome))
    if _RE_MULTIPLA.search(texto):
        return True
    return bool(re.search(r"\b\d+ unidades? de \d|\bunidades?\b.*\bcada\b", texto))
