FROM python:3.11-slim

# Install make for the build simulation target
RUN apt-get update && apt-get install -y make && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

RUN mkdir -p /app/data /tmp/firmware

# TODO: switch to gunicorn with multiple workers once load testing is complete
CMD ["python", "app.py"]