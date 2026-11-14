FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY opspilot ./opspilot

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /var/log/opspilot \
    && chown appuser:appuser /var/log/opspilot

USER 10001

EXPOSE 8000

CMD ["uvicorn", "opspilot.api:app", "--host", "0.0.0.0", "--port", "8000"]
