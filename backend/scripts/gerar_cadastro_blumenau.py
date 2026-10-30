"""Gera db/dados/01_blumenau.sql: bairros, redes e lojas de Blumenau.

Fontes (consultadas uma vez, quando o script roda; o SQL gerado vai para o repositório):
- Lojas com preço on-line: pontos de retirada públicos das próprias redes (VTEX), com endereço e coordenadas
  oficiais. Têm prioridade: em 2026-10-28 o OpenStreetMap tinha o Angeloni Velha 2,7 km fora do lugar.
- Bairros (limites e centro, R14) e lojas das redes sem site: OpenStreetMap, © colaboradores do OpenStreetMap,
  licença ODbL (a atribuição aparece na tela "Sobre" do app).
- Das lojas do OpenStreetMap entram só as redes da lista REDES_OSM (atacarejos e redes com 2 ou mais lojas).
  Ficam com origem 'openstreetmap' até alguém confirmar no local.

Rodar:  python scripts/gerar_cadastro_blumenau.py   (faz umas 6 requisições, respeitando robots.txt)
"""

import json
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantofica.coleta.redes import NOME_NO_BANCO, REDES_VTEX  # noqa: E402
from quantofica.coleta.vtex import AGENTE, ClienteHttp  # noqa: E402

SAIDA = Path(__file__).resolve().parents[2] / "db" / "dados" / "01_blumenau.sql"
OVERPASS = "https://overpass-api.de/api/interpreter"
ESPACO = uuid.UUID("6f1b9a52-4c1e-4f0e-9d1a-7a0b8c3d2e10")  # ids estáveis: rodar de novo atualiza em vez de duplicar

SITES = {
    "giassi": "www.giassi.com.br",
    "cooper": "www.minhacooper.com.br",
    "angeloni": "super.angeloni.com.br",
    "sams": "www.samsclub.com.br",
}
# Redes com coleta própria fora da VTEX (o Vigia acompanha toda rede com site).
SITES_POR_NOME = {"Rede Top": "www.redetoponline.com.br", "Fort Atacadista": "www.fortatacadista.com.br"}

# Nome no OpenStreetMap (minúsculas) -> rede. Lojas da Cooper fora do site entram na rede Cooper, sem preço on-line.
# A loja recebe o nome "Rede Bairro", menos as que têm nome próprio (NOMES_PROPRIOS).
REDES_OSM = {
    "fort atacadista": "Fort Atacadista",
    "komprão koch atacadista": "Komprão",
    "atacadão": "Atacadão",
    "brasil atacadista": "Brasil Atacadista",
    "super a atacadista": "Super A Atacadista",
    "cooper atacarejo": "Cooper",
    "cooper glória": "Cooper",
    "cooper super omino": "Cooper",
    "bistek supermercados": "Bistek",
    "rede top supermercados": "Rede Top",
    "super ferreira": "Super Ferreira",
    "casa express": "Casa Express",
    "supermercado mavili": "Mavili",
    "supermercados carol": "Carol",
    "unibox dinardelli": "Unibox",
}
NOMES_PROPRIOS = {"cooper atacarejo": "Cooper Atacarejo", "cooper glória": "Cooper Glória", "cooper super omino": "Cooper Omino"}
NOMES_REDE = {"Sam´s Blumenau-B.Velha": "Sam's Club Blumenau"}

CONSULTA_BAIRROS = """[out:json][timeout:90];
area["name"="Blumenau"]["admin_level"="8"]->.cidade;
relation["boundary"="administrative"]["admin_level"="10"](area.cidade);
out geom;"""

CONSULTA_MERCADOS = """[out:json][timeout:90];
area["name"="Blumenau"]["admin_level"="8"]->.cidade;
nwr["shop"~"supermarket|wholesale"](area.cidade);
out tags center;"""


def overpass(consulta: str) -> list[dict]:
    corpo = urllib.parse.urlencode({"data": consulta}).encode()
    for espera in (0, 10, 30, 60):  # o servidor público pede recuo quando está cheio
        time.sleep(espera)
        try:
            req = urllib.request.Request(OVERPASS, data=corpo, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())["elements"]
        except (urllib.error.HTTPError, json.JSONDecodeError):
            continue
    raise RuntimeError("Overpass indisponível")


def aneis(membros: list[dict]) -> list[list[tuple[float, float]]]:
    """Junta os trechos 'outer' de um limite em anéis fechados de (lon, lat)."""
    trechos = [[(p["lon"], p["lat"]) for p in m["geometry"]] for m in membros if m.get("role") == "outer" and m.get("geometry")]
    prontos = []
    while trechos:
        anel = trechos.pop(0)
        while anel[0] != anel[-1]:
            for i, t in enumerate(trechos):
                if t[0] == anel[-1]:
                    anel += t[1:]
                elif t[-1] == anel[-1]:
                    anel += t[::-1][1:]
                else:
                    continue
                trechos.pop(i)
                break
            else:
                break  # anel aberto (dado incompleto): fica como está
        prontos.append(anel)
    return prontos


def area_e_centro(anel):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1], strict=True):
        f = x1 * y2 - x2 * y1
        a, cx, cy = a + f, cx + (x1 + x2) * f, cy + (y1 + y2) * f
    a /= 2
    return abs(a), (cx / (6 * a), cy / (6 * a)) if a else anel[0]


def dentro(ponto, anel) -> bool:
    x, y = ponto
    achou = False
    for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            achou = not achou
    return achou


def texto(v) -> str:
    return "null" if v is None else "'" + str(v).replace("'", "''") + "'"


def main() -> None:
    bairros = []
    for rel in overpass(CONSULTA_BAIRROS):
        partes = [area_e_centro(a) + (a,) for a in aneis(rel["members"])]
        total = sum(p[0] for p in partes)
        lon = sum(p[0] * p[1][0] for p in partes) / total
        lat = sum(p[0] * p[1][1] for p in partes) / total
        bairros.append({"nome": rel["tags"]["name"], "lat": lat, "lon": lon, "aneis": [p[2] for p in partes]})
    bairros.sort(key=lambda b: b["nome"])

    def bairro_de(lat, lon):
        return next((b["nome"] for b in bairros if any(dentro((lon, lat), a) for a in b["aneis"])), None)

    lojas = []
    http = ClienteHttp()
    for rede in REDES_VTEX:
        resp = http(f"https://{rede.dominio}/api/checkout/pub/pickup-points?postalCode={rede.cep}&countryCode=BRA", None) or {}
        vistos = set()
        for item in resp.get("items", []):
            p = item["pickupPoint"]
            end = p["address"]
            seller = p["id"].split("_", 1)[0]  # "samsclub4001_P4001_1" -> "samsclub4001"
            if end.get("city") != "Blumenau" or not seller.startswith(("giassi", "minhacooper", "superangeloni", "samsclub")):
                continue  # o Angeloni repete cada loja com um id numérico; fica o que tem o nome do seller
            if seller in vistos:
                continue
            vistos.add(seller)
            lon, lat = end["geoCoordinates"]
            lojas.append(
                {
                    "id": uuid.uuid5(ESPACO, f"vtex:{seller}"),
                    "rede": NOME_NO_BANCO[rede.id],
                    "nome": NOMES_REDE.get(p["friendlyName"], p["friendlyName"].replace(" Blumenau", "")),
                    "endereco": f"{end['street']}, {end['number']} - {end['neighborhood']}",
                    "lat": lat,
                    "lon": lon,
                    "seller": seller,
                    "origem": "rede",
                    "bairro": bairro_de(lat, lon),
                }
            )
    online = [lj for lj in lojas if lj["rede"] == "Cooper"]

    for e in overpass(CONSULTA_MERCADOS):
        t = e["tags"]
        nome_osm = (t.get("name") or "").lower()
        rede = REDES_OSM.get(nome_osm)
        if not rede:
            continue
        c = e.get("center") or {"lat": e["lat"], "lon": e["lon"]}
        b = bairro_de(c["lat"], c["lon"])
        if rede == "Cooper" and any(lj["bairro"] == b for lj in online):
            continue  # já veio da própria rede
        rua = " ".join(filter(None, [t.get("addr:street"), t.get("addr:housenumber")]))
        lojas.append(
            {
                "id": uuid.uuid5(ESPACO, f"osm:{e['type']}/{e['id']}"),
                "rede": rede,
                "nome": NOMES_PROPRIOS.get(nome_osm) or (f"{rede} {b}" if b else rede),
                "rua": t.get("addr:street"),
                "endereco": f"{rua} - {b}" if rua and b else (rua or None),
                "lat": c["lat"],
                "lon": c["lon"],
                "seller": None,
                "origem": "openstreetmap",
                "bairro": b,
            }
        )
    # Duas lojas da mesma rede no mesmo bairro: a rua desempata ("Rede Top Itoupava Central · Rua Gustavo Zimmermann").
    contagem: dict[str, int] = {}
    for lj in lojas:
        contagem[lj["nome"]] = contagem.get(lj["nome"], 0) + 1
    for lj in lojas:
        if contagem[lj["nome"]] > 1:
            if not lj.get("rua"):
                raise RuntimeError(f"duas lojas chamadas {lj['nome']!r} e uma sem rua para desempatar")
            lj["nome"] = f"{lj['nome']} · {lj['rua']}"
    lojas.sort(key=lambda lj: (lj["rede"], lj["nome"]))
    escrever(bairros, lojas)
    print(f"{len(bairros)} bairros e {len(lojas)} lojas em {SAIDA}")


def escrever(bairros, lojas) -> None:
    linhas = [
        "-- Gerado por backend/scripts/gerar_cadastro_blumenau.py. Não edite à mão: rode o script de novo.",
        "-- Bairros e lojas sem site: © colaboradores do OpenStreetMap (ODbL). Lojas com site: dados públicos das redes.",
        "begin;",
        "insert into cidade (nome, uf) values ('Blumenau', 'SC') on conflict (nome, uf) do nothing;",
        "",
    ]
    for b in bairros:
        linhas.append(
            "insert into bairro (cidade_id, nome, lat_centro, lon_centro) "
            f"select id, {texto(b['nome'])}, {b['lat']:.6f}, {b['lon']:.6f} from cidade where nome = 'Blumenau' "
            "on conflict (cidade_id, nome) do update set lat_centro = excluded.lat_centro, lon_centro = excluded.lon_centro;"
        )
    linhas.append("")
    for rede in sorted({lj["rede"] for lj in lojas}):
        chave = next((k for k, v in NOME_NO_BANCO.items() if v == rede), None)
        site = SITES.get(chave) if chave else SITES_POR_NOME.get(rede)
        linhas.append(
            f"insert into rede (nome, site, tem_api) values ({texto(rede)}, {texto(site)}, {'true' if site else 'false'}) "
            "on conflict (nome) do update set site = excluded.site, tem_api = excluded.tem_api;"
        )
    linhas.append("")
    for lj in lojas:
        linhas.append(
            "insert into loja (id, rede_id, cidade_id, bairro_id, nome, endereco, lat, lon, seller_id, origem) "
            f"select {texto(lj['id'])}, r.id, c.id, b.id, {texto(lj['nome'])}, {texto(lj['endereco'])}, "
            f"{lj['lat']:.6f}, {lj['lon']:.6f}, {texto(lj['seller'])}, {texto(lj['origem'])} "
            f"from rede r cross join cidade c left join bairro b on b.cidade_id = c.id and b.nome = {texto(lj['bairro'])} "
            f"where r.nome = {texto(lj['rede'])} and c.nome = 'Blumenau' "
            "on conflict (id) do update set nome = excluded.nome, endereco = excluded.endereco, lat = excluded.lat, "
            "lon = excluded.lon, bairro_id = excluded.bairro_id, seller_id = excluded.seller_id;"
        )
    linhas += ["commit;", ""]
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")


if __name__ == "__main__":
    main()
