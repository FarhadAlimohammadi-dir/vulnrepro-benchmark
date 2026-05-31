FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
COPY utils/ utils/
COPY services/ services/
COPY models/ models/
COPY templates/ templates/
COPY static/ static/
CMD ["python", "app.py"]