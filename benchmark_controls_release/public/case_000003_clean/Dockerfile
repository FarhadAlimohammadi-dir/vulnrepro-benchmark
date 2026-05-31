FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

ENV FLASK_ENV=development
ENV PORT=9000
ENV ANTHROPIC_API_KEY=sk-ant-api03-placeholder-dev-key

EXPOSE 9000

CMD ["python", "app.py"]