FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ripgrep git findutils grep coreutils golang-go ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask==3.0.3

RUN mkdir -p /data \
    /workspace/backend-api \
    /workspace/frontend-app \
    /workspace/ml-pipeline \
    /workspace/infra-terraform \
    /workspace/docs-site \
    /workspace/mobile-ios \
    /workspace/mobile-android \
    /workspace/data-warehouse \
    /workspace/auth-service \
    /workspace/notification-svc

WORKDIR /app
COPY app/ /app/

RUN python /app/db.py

EXPOSE 9000

ENV PORT=9000 \
    DB_PATH=/data/devflow.db \
    SECRET_KEY=devflow-docker-secret

CMD ["python", "/app/app.py"]