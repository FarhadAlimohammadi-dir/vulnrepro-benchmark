FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
COPY services/ services/
COPY middleware/ middleware/
COPY utils/ utils/
COPY templates/ templates/
COPY static/ static/
CMD ["python", "app.py"]