FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

ENV PORT=9000
ENV PYTHONUNBUFFERED=1

EXPOSE 9000

CMD ["python", "app.py"]