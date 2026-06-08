FROM python:3.11-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY prompts ./prompts
COPY data ./data
RUN uv sync --frozen --no-dev
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "trade_sentinel_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
