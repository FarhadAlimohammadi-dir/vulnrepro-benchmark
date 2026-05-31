FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

RUN mkdir -p /workspace/.project /data

ENV WORKSPACE=/workspace
ENV DB_PATH=/data/codereview.db
ENV PORT=9000

EXPOSE 9000

CMD ["python", "entrypoint.py"]