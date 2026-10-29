"""Páginas web: a lista aberta pelo link do convite (14) e o painel interno de revisão."""

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
