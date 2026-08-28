FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt


FROM python:3.12-slim

RUN addgroup --system sentinel && adduser --system --ingroup sentinel sentinel

WORKDIR /app

COPY --from=builder /install /usr/local

COPY --chown=sentinel:sentinel . .

USER sentinel

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]