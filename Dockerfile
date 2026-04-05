FROM python:3.12-slim-bookworm

WORKDIR /app

# CJK font for heatmap image rendering (single file, no apt needed)
RUN mkdir -p /usr/share/fonts/noto && \
    python -c "import urllib.request; urllib.request.urlretrieve( \
      'https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf', \
      '/usr/share/fonts/noto/NotoSansCJKjp-Regular.otf')"

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
