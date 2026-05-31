FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
RUN mkdir -p /data
ENV DB_PATH=/data/documind.db
ENV PORT=9000
ENV SECRET_KEY=documind-prod-secret-9x2k
EXPOSE 9000
CMD ["python", "-m", "app.main"]