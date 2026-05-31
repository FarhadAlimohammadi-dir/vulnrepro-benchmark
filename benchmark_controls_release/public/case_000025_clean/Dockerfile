FROM python:3.12-slim
WORKDIR /srv
RUN pip install --no-cache-dir flask==3.0.3 Werkzeug==3.0.3
COPY . /srv/
EXPOSE 9000
CMD ["python", "run.py"]