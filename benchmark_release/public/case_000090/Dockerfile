FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/data /app/instance

ENV FLASK_APP=app
ENV FLASK_ENV=production
ENV DATABASE_PATH=/app/data/themes.db

EXPOSE 9000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=9000"]