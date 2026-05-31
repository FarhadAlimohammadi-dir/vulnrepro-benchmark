FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

RUN mkdir -p /app/data

CMD ["sh", "-c", "python db.py && gunicorn --bind 0.0.0.0:9000 --workers 2 --timeout 60 app:app"]