FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl sqlite3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app
ENV FLASK_ENV=production
ENV SECRET_KEY=relay-service-prod-key-2024

EXPOSE 9000

CMD ["python", "run.py"]