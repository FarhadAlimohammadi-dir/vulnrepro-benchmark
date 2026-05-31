FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "from app import create_app, db; app = create_app(); \
    ctx = app.app_context(); ctx.push(); db.seed_data()"

EXPOSE 9000

CMD ["python", "run.py"]