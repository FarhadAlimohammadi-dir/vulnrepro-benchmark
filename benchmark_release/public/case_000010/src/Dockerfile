FROM python:3.12-slim
WORKDIR /app
COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .
EXPOSE 9000
CMD ["python", "app.py"]