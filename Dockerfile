# Use a slim Python image; you can pin version if you like
FROM python:3.11-slim

# Set workdir inside container
WORKDIR /app

# Install system dependencies (for psycopg2/postgres, sqlite, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better layer caching)
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Environment: default to SQLite dev
ENV DB_TYPE=sqlite

# Optionally set Python buffer and env (good for logs)
ENV PYTHONUNBUFFERED=1

# Start the app (run.py should start uvicorn)
CMD ["python", "run.py"]