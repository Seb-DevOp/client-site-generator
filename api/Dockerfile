FROM python:3.9-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip
RUN pip install flask google-cloud-build google-cloud-run gunicorn

EXPOSE 8080

CMD exec gunicorn --bind :$PORT main:app
