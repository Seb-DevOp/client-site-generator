FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y gcc g++ libffi-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]