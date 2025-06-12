FROM python:3.13-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=2

ARG GIT_TOKEN
RUN test -n "$GIT_TOKEN" || { echo "GIT_TOKEN не установлен"; exit 1; }

RUN apt-get update
RUN apt-get install -y --no-install-recommends git curl gcc build-essential
RUN git config --global url."https://oauth2:${GIT_TOKEN}@github.com".insteadOf "https://github.com"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN cp /root/.local/bin/uv /usr/local/bin
RUN rm -rf /root/.local
RUN apt-get purge -y --auto-remove curl
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --compile --no-dev --no-cache

FROM python:3.13-slim-bookworm AS production

ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=2

ENV PATH="/venv/bin:$PATH"
COPY --from=builder /app/.venv /venv

WORKDIR /app
COPY ./src .

RUN python -m compileall /app
