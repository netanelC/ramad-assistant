FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration and project files
COPY pyproject.toml README.md doctrine.md ./
COPY *.csv ./
COPY data/ ./data/
COPY src/ ./src/

# Install application
RUN pip install --no-cache-dir .

# Create volume mount point for persistent SQLite database
RUN mkdir -p /data
ENV DATABASE_URL="sqlite:////data/ramad_tasks.db"

EXPOSE 8080

ENTRYPOINT ["python", "-m", "ramad_assistant.main"]
