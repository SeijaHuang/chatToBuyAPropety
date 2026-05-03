# Stage 1: builder — installs dependencies using uv
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .

RUN uv sync --frozen --no-dev

# Stage 2: runtime — lean image with only the virtual environment and app code
FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
