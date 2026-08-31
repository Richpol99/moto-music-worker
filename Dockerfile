FROM nikolaik/python-nodejs:python3.10-nodejs18-slim

RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    ca-certificates \
    ffmpeg \
    && curl https://rclone.org/install.sh | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["python", "app.py"]
