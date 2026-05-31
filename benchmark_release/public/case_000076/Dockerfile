FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Application source
COPY app.py .
COPY services/ services/
COPY middleware/ middleware/
COPY templates/ templates/
COPY static/ static/

# Seed static file tree
RUN mkdir -p /app/static/files && \
    echo "Welcome to OldBlog static files" > /app/static/files/readme.txt && \
    echo "OldBlog changelog: v1.4.2 - minor fixes" > /app/static/files/changelog.txt

EXPOSE 9000

CMD ["python", "app.py"]