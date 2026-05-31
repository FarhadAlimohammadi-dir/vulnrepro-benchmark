FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python -c "from app import create_app; app = create_app(); ctx = app.app_context(); ctx.push(); from app.models import init_db, seed_db; init_db(); seed_db()"

EXPOSE 9000

CMD ["python", "run.py"]