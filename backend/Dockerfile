# Imagem da API. Contexto do build: a raiz do repositório (ver render.yaml).
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências primeiro: mudar o código não reinstala tudo.
COPY backend/pyproject.toml backend/
COPY backend/src backend/src
RUN pip install ./backend

# Migrações e dados iniciais (python -m quantofica.banco.migrar --dados).
COPY db/migrations db/migrations
COPY db/dados db/dados

# Não roda como root.
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080
# O Render informa a porta em $PORT; localmente vale 8080.
CMD uvicorn quantofica.api.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}
