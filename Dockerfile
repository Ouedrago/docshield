# Dockerfile
# ----------
# Packages DocShield into a production-ready container image.
#
# Why Docker?
# Docker ensures the app runs identically everywhere - your laptop,
# AWS ECS, a colleague's machine. No more "works on my machine" problems.
# Every dependency, every config file, every Python package is baked
# into the image at build time.
#
# Build with: docker build -t docshield .
# Run locally: docker run -p 8501:8501 --env-file .env docshield

# --- BASE IMAGE ---
FROM python:3.12-slim

# --- METADATA ---
LABEL maintainer="DocShield"
LABEL description="Secure Document Intelligence powered by AWS Bedrock"
LABEL version="1.0.0"

# --- SYSTEM DEPENDENCIES ---
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# --- WORKING DIRECTORY ---
WORKDIR /app

# --- PYTHON DEPENDENCIES ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- APPLICATION CODE ---
COPY app/ ./app/

# --- DIRECTORIES ---
RUN mkdir -p local_index sample_docs

# --- STREAMLIT CONFIG ---
RUN mkdir -p .streamlit && printf '[server]\nheadless = true\nport = 8501\naddress = "0.0.0.0"\nenableCORS = false\nenableXsrfProtection = true\n\n[browser]\ngatherUsageStats = false\n' > .streamlit/config.toml

# --- PORT ---
EXPOSE 8501

# --- HEALTH CHECK ---
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# --- STARTUP COMMAND ---
CMD ["python", "-m", "streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]