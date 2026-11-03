# Use an official, lightweight Python image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for compiling certain packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for rapid, reliable dependency installation
RUN pip install --no-cache-dir uv

# Copy dependency specifications first to leverage Docker layer caching
COPY Telemetry-API/pyproject.toml ./
# If you have uv.lock or requirements.txt, copy it too:
COPY Telemetry-API/uv.lock ./

# Install dependencies into the system environment inside the container
RUN uv pip install --system -r pyproject.toml

# Copy application source code
COPY Telemetry-API/ /app/

# Expose FastAPI default port
EXPOSE 8000

# Run Uvicorn directly (production-style multi-worker can be tuned here)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]