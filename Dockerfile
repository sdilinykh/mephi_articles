FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV DATABASE_URL=postgresql+psycopg://mephi:mephi@postgres:5432/mephi_journals
