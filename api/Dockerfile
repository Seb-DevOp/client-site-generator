FROM python:3.10-slim

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y gcc \
 && pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir flask google-cloud-build google-cloud-storage

EXPOSE 8080

CMD ["python", "main.py"]
