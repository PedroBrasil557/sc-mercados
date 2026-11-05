"""Encarte pela camada de texto do Issuu: protobuf com o texto, o tamanho e a posição de cada trecho."""

import gzip
import struct
from datetime import date

from quantofica.coleta import encarte_issuu


def _varint(n: int) -> bytes:
    saida = b""
    while True:
        b, n = n & 0x7F, n >> 7
        saida += bytes([b | (0x80 if n else 0)])
        if not n:
            return saida


def _campo(numero: int, valor: bytes) -> bytes:
    return _varint(numero << 3 | 2) + _varint(len(valor)) + valor


def _trecho(texto: str, escala: float, x: float, y: float, avanco: float = 28.0) -> bytes:
    """Um trecho como o Issuu grava: texto sem os espaços (1), fonte 50 (3), matriz (5) e o início de cada letra (6),
    com o vão do espaço entre as palavras."""
    posicoes, pos = [], 0.0
    for c in texto:
        if c == " ":
            pos += 14.0
            continue
        posicoes.append(pos)
        pos += avanco
    texto = texto.replace(" ", "")
    letras = struct.pack(f"<{len(texto)}f", *posicoes)
    corpo = _campo(1, texto.encode()) + bytes([0x1D]) + struct.pack("<f", 50.0)
    corpo += _campo(5, struct.pack("<6f", escala, 0, 0, escala, x, y)) + _campo(6, letras)
    return _campo(9, _campo(2, corpo))


def _camada(*trechos: bytes) -> bytes:
    return gzip.compress(b"\x08\x01" + b"".join(trechos))


def test_cartao_com_nome_preco_e_preco_do_clube():
    camada = _camada(
        _trecho("Margarina", 0.52, 100, 1000),
        _trecho("BECEL", 0.52, 100, 1026),
        _trecho("500gun.", 0.462, 100, 1050),
        _trecho("R$", 0.578, 330, 1052),
        _trecho("7", 1.848, 360, 1052),
        _trecho(",", 0.924, 410, 1052),
        _trecho("99", 1.617, 418, 1046),
        _trecho("Preços válidos de 02/11 a 06/11/2026 ou enquanto durarem os estoques", 0.5, 100, 2900),
    )
    pagina = encarte_issuu.ler_camada(camada, 1, 1965, date(2026, 10, 30))
    assert [(i.nome, i.preco_centavos) for i in pagina.itens] == [("Margarina BECEL 500g un.", 799)]
    assert pagina.validade == (date(2026, 11, 2), date(2026, 11, 6))


def test_largura_da_letra_ignora_o_espaco_que_vem_depois():
    # "g" quase sempre antes de espaço (avanço grande), uma vez dentro da palavra: a largura é a de dentro.
    assert encarte_issuu._largura([0.5, 0.78, 0.8, 0.79]) == 0.5
    assert encarte_issuu._largura([0.55, 0.5, 0.56]) == 0.55  # ajuste fino ("RA"): um grupo só


def test_largura_do_jpeg_pelo_cabecalho():
    jpeg = b"\xff\xd8" + b"\xff\xe0\x00\x10" + b"J" * 14 + b"\xff\xc0\x00\x11\x08\x0b\xae\x08\xcd" + b"\x00" * 12
    assert encarte_issuu.largura_do_jpeg(jpeg) == 2253
