# --- Stage 1: Builder ---
# This stage builds the Python dependencies
FROM python:3.11-slim as builder

# Install build-time system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up a virtual environment
WORKDIR /app
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=600 -r requirements.txt


# --- Stage 2: Final Image ---
# This stage creates the final, lean runtime image
FROM python:3.11-slim

# Install only runtime system dependencies (psycopg2 needs libpq)
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd -m -u 1000 appuser
WORKDIR /home/appuser
USER appuser

# Copy the virtual environment from the builder stage
COPY --chown=appuser:appuser --from=builder /app/venv ./venv

# Copy application code and necessary files
COPY --chown=appuser:appuser ./src ./src
COPY --chown=appuser:appuser ./migrations ./migrations
COPY --chown=appuser:appuser gunicorn.conf.py .

# Set environment variables
ENV PATH="/home/appuser/venv/bin:$PATH"
ENV PYTHONPATH=/home/appuser
ENV FLASK_APP=src.main

# Expose port
EXPOSE 5000

# Start the app with Gunicorn
CMD ["gunicorn", "--config", "./gunicorn.conf.py", "src.main:app"]