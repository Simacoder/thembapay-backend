# Deploy this to Render as a Docker web service (not the default Python
# buildpack) so Tesseract's system binary actually gets installed -
# `pip install -r requirements.txt` alone cannot do this, since
# pytesseract is just a Python wrapper around a separate OS program.

FROM python:3.11-slim

# Install Tesseract OCR (system binary) and poppler-utils (needed by
# pdf2image, if you ever process PDF invoices instead of just images)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# IMPORTANT - see the ledger persistence note in the deployment README
# section: this container's filesystem, including data/ledger.db, resets
# on every restart/redeploy on Render's free tier. Fine for a live pitch
# demo (you control exactly when it restarts); NOT fine for claiming a
# permanent audit trail without saying so.

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
