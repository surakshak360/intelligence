FROM python:3.11-slim

WORKDIR /app

# System deps (networkx/scikit-learn/reportlab are pure-Python + wheels;
# libgl1 kept for parity with the shared template even though this
# service does no image work).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /tmp/surakshak360_evidence && \
    chown -R appuser:appuser /app /tmp/surakshak360_evidence
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
