"""Leitura de robots.txt com curingas (* e $), como o Google interpreta.

O urllib.robotparser da biblioteca padrão compara só prefixos e ignora "*": regras como
"Disallow: *?fq=*" do Angeloni passariam despercebidas. Respeitar o robots.txt é regra de coleta
da especificação (Fontes de dados) e da política da Play Store (não violar termos de serviços).
"""

import re
from dataclasses import dataclass, field


@dataclass
class Regras:
    permitir: list[str] = field(default_factory=list)
    proibir: list[str] = field(default_factory=list)

    def permitido(self, caminho: str) -> bool:
        """Vale a regra mais específica (padrão mais longo); em empate, Allow vence."""
        melhor_tam, melhor = -1, True
        for padrao, permitido in [(p, True) for p in self.permitir] + [(p, False) for p in self.proibir]:
            if padrao and _casa(padrao, caminho):
                if len(padrao) > melhor_tam or (len(padrao) == melhor_tam and permitido):
                    melhor_tam, melhor = len(padrao), permitido
        return melhor


def _casa(padrao: str, caminho: str) -> bool:
    if not padrao.startswith(("/", "*")):
        padrao = "/" + padrao
    ancorado = padrao.endswith("$")
    corpo = re.escape(padrao.rstrip("$")).replace(r"\*", ".*")
    return re.match(corpo + ("$" if ancorado else ""), caminho) is not None


def ler(texto: str, agente: str = "*") -> Regras:
    """Regras do grupo do agente (ou do grupo "*")."""
    grupos: dict[str, Regras] = {}
    atuais: list[str] = []
    lendo_agentes = False
    for linha in texto.splitlines():
        linha = linha.split("#", 1)[0].strip()
        if ":" not in linha:
            continue
        chave, valor = (p.strip() for p in linha.split(":", 1))
        chave = chave.lower()
        if chave == "user-agent":
            if not lendo_agentes:
                atuais = []
            atuais.append(valor.lower())
            grupos.setdefault(valor.lower(), Regras())
            lendo_agentes = True
            continue
        lendo_agentes = False
        for a in atuais:
            if chave == "allow":
                grupos[a].permitir.append(valor)
            elif chave == "disallow":
                grupos[a].proibir.append(valor)
    return grupos.get(agente.lower()) or grupos.get("*") or Regras()
