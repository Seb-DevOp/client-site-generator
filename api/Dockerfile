FROM python:3.9-slim

WORKDIR /api

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install google-cloud-build flask gunicorn google-cloud-run google-api-core

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
