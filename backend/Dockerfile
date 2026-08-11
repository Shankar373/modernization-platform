FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for Maven/Java detection, git, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl openjdk-17-jdk-headless maven \
    && rm -rf /var/lib/apt/lists/*

# Install Ruff
RUN pip install ruff

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
