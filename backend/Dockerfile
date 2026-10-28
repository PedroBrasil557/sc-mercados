# Imagem da API e do relógio da coleta. Contexto do build: a raiz do repositório (ver fly.toml).
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

# Migrações e dados iniciais, usados pelo release_command a cada publicação.
COPY db/migrations db/migrations
COPY db/dados db/dados

# Não roda como root.
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8080
CMD ["uvicorn", "quantofica.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
