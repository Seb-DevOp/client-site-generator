FROM python:3.10-slim

WORKDIR /app
COPY main.py /app

RUN pip install --no-cache-dir \
    flask \
    google-cloud-build==3.12.0 \
    protobuf==4.25.3

EXPOSE 8080
CMD ["python", "main.py"]
