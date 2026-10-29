"""Páginas web: a lista do convite (14), o painel interno e os textos legais (privacidade, termos, exclusão)."""

import html
import os
import secrets
from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])

_LISTA = files(__package__).joinpath("lista.html").read_text(encoding="utf-8")
_PAINEL = files(__package__).joinpath("painel.html").read_text(encoding="utf-8")


def _pagina(modelo: str) -> HTMLResponse:
    # Cada resposta tem um nonce novo: só o script e o estilo da própria página rodam (nada injetado).
    nonce = secrets.token_urlsafe(16)
    return HTMLResponse(
        modelo.replace("{{NONCE}}", nonce),
        headers={
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        },
    )


@router.get("/c/{codigo}", response_class=HTMLResponse, include_in_schema=False)
def lista_na_web(codigo: str):
    return _pagina(_LISTA)


@router.get("/painel", response_class=HTMLResponse, include_in_schema=False)
def painel():
    return _pagina(_PAINEL)


# Páginas exigidas pelo Google Play: política de privacidade, termos e exclusão de dados pela web.
_DOCUMENTO = files(__package__).joinpath("documento.html").read_text(encoding="utf-8")
VERSAO_DOS_TEXTOS = "29 de outubro de 2026"


def _documento(titulo: str, arquivo: str) -> HTMLResponse:
    corpo = files(__package__).joinpath(arquivo).read_text(encoding="utf-8")
    texto = _DOCUMENTO.replace("{{TITULO}}", titulo).replace("{{CORPO}}", corpo)
    for chave, valor in {
        "{{RESPONSAVEL}}": os.environ.get("RESPONSAVEL_NOME", "o responsável pelo SC Mercados"),
        "{{CONTATO}}": os.environ.get("CONTATO_EMAIL", "e-mail de contato em breve"),
        "{{DATA}}": VERSAO_DOS_TEXTOS,
    }.items():
        texto = texto.replace(chave, html.escape(valor))
    return _pagina(texto)


@router.get("/privacidade", response_class=HTMLResponse, include_in_schema=False)
def privacidade():
    return _documento("Privacidade", "privacidade.html")


@router.get("/termos", response_class=HTMLResponse, include_in_schema=False)
def termos():
    return _documento("Termos de uso", "termos.html")


@router.get("/excluir-conta", response_class=HTMLResponse, include_in_schema=False)
def excluir_conta():
    return _documento("Apagar meus dados", "excluir.html")
