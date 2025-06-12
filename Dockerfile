FROM python:3.13-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1

ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=2

ARG GIT_TOKEN
RUN test -n "$GIT_TOKEN" || { echo "GIT_TOKEN не установлен"; exit 1; }

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl gcc build-essential && \
    git config --global url."https://oauth2:${GIT_TOKEN}@github.com".insteadOf "https://github.com" && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin && \
    rm -rf /root/.local && \
    apt-get purge -y --auto-remove curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --compile --no-dev

FROM python:3.13-slim-bookworm AS production

ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=2

ENV PATH="/venv/bin:$PATH"
COPY --from=builder /app/.venv /venv

WORKDIR /app
COPY ./src .

RUN python -m compileall /app
