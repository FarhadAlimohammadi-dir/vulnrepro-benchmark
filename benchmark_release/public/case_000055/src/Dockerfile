FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# NOTE: gunicorn preferred in production; plain flask used here for simplicity
CMD ["python", "app.py"]