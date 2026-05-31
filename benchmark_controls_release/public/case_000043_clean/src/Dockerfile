FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app/main.py
ENV FLASK_ENV=production
ENV DATABASE_PATH=/data/githost.db

RUN mkdir -p /data

EXPOSE 9000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=9000"]