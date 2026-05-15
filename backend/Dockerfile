# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Системные зависимости: bcrypt/passlib собирается из бинарного wheel,
# fonts-dejavu-core нужен для рендера кириллицы в PDF-чеках (reportlab).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала requirements — кеш слой
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Копируем приложение
COPY app ./app
COPY scripts ./scripts

# Каталоги для пользовательских файлов (uploads, receipts) и SQLite-БД.
# Их монтируют как volume в docker-compose.yml.
RUN mkdir -p /app/uploads /app/receipts /app/data

ENV UPLOADS_DIR=/app/uploads \
    RECEIPTS_DIR=/app/receipts \
    DATABASE_URL=sqlite:////app/data/clothing_sales.db

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
