"""14 Lista na web: a página aberta pelo link do convite, para quem não tem o app."""

import secrets
from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])

_MODELO = files(__package__).joinpath("lista.html").read_text(encoding="utf-8")


@router.get("/c/{codigo}", response_class=HTMLResponse, include_in_schema=False)
def lista_na_web(codigo: str):
    # Cada resposta tem um nonce novo: só o script e o estilo da própria página rodam (nada injetado).
    nonce = secrets.token_urlsafe(16)
    return HTMLResponse(
        _MODELO.replace("{{NONCE}}", nonce),
        headers={
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        },
    )
