"""Redes de Blumenau com API VTEX pública (validado em 22/10/2026)."""

from ..regras.preco import Faixa
from .vtex import Rede

CEP_BLUMENAU = "89010000"

REDES_VTEX = [
    Rede("giassi", "www.giassi.com.br", CEP_BLUMENAU),
    Rede(
        "cooper",
        "www.minhacooper.com.br",
        CEP_BLUMENAU,
        filtro_seller="blumenau",  # o CEP devolve lojas de Jaraguá, Joinville, Indaial...
        nomes_sellers={
            "minhacoopersuperaguaverdeblumenau": "Água Verde",
            "minhacoopersupergarciablumenau": "Garcia",
            "minhacoopersuperitoupavanorteblumenau": "Itoupava Norte",
            "minhacoopersupermafisablumenau": "Mafisa",
            "minhacoopersupervilanovablumenau": "Vila Nova",
            "minhacoopersupervorstadtblumenau": "Vorstadt",
        },
    ),
    Rede("angeloni", "super.angeloni.com.br", CEP_BLUMENAU),  # robots proíbe fq=: o coletor cai na busca inteligente
    Rede("sams", "www.samsclub.com.br", CEP_BLUMENAU),
]

# Nome da rede na tabela `rede`.
NOME_NO_BANCO = {"giassi": "Giassi", "cooper": "Cooper", "angeloni": "Angeloni", "sams": "Sam's Club"}

# Sam's Club exige ser sócio: o preço é de clube, que só aparece depois do lançamento (R5).
FAIXA = {"sams": Faixa.CLUBE}
