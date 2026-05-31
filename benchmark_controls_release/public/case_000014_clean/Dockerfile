FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir flask==3.0.3 Werkzeug==3.0.3
COPY app/ /app/
ENV PORT=9000
ENV DB_PATH=/tmp/promptforge.db
EXPOSE 9000
CMD ["python", "/app/app.py"]