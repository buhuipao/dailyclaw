FROM python:3.12-slim

WORKDIR /app

# CJK font for heatmap image rendering
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY src/ src/
COPY templates/ templates/

# Data dir for SQLite + media
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
