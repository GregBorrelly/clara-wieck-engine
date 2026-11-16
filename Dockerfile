FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bake the model weights (about 150 MB) into the image so the first request isn't slow.
RUN homr --init --no-title
COPY reader ./reader
# Port 80 unless PORT says otherwise (Vercel sends traffic to 80; other hosts set PORT themselves).
ENV PORT=80
EXPOSE 80
CMD ["sh", "-c", "uvicorn reader.app:app --host 0.0.0.0 --port ${PORT} --workers 1"]
