FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./

RUN mkdir -p /data

ENV DATABASE=/data/pipelineforge.db
ENV PORT=9000
ENV SECRET_KEY=pf-prod-secret-change-me

EXPOSE 9000

CMD ["sh", "-c", "python db.py && python app.py"]