FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install flask google-cloud-build

EXPOSE 5000
CMD ["python", "main.py"]
