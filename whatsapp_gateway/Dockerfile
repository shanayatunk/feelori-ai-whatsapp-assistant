# --- Stage 1: Builder ---
# This stage builds the Python dependencies
FROM python:3.11.9-slim as builder

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
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
# This stage creates the final, lean runtime image
FROM python:3.11.9-slim

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for improved security
RUN useradd -m -u 1000 appuser
WORKDIR /home/appuser
USER appuser

# Copy the virtual environment from the builder stage
COPY --chown=appuser:appuser --from=builder /app/venv ./venv

# Copy application code and necessary files
COPY --chown=appuser:appuser ./src ./src
COPY --chown=appuser:appuser ./migrations ./migrations
COPY --chown=appuser:appuser ./entrypoint.sh .

# Make the entrypoint script executable
RUN chmod +x ./entrypoint.sh

# Set environment variables for the application
ENV PATH="/home/appuser/venv/bin:$PATH"
ENV PYTHONPATH=/home/appuser/
ENV FLASK_APP=src.main

# Expose the port the application will run on
EXPOSE 5000

# Use the entrypoint script to run migrations and then start the application
ENTRYPOINT ["./entrypoint.sh"]

# The default command to start the application with Hypercorn
CMD ["hypercorn", "src.main:app", "--bind", "0.0.0.0:5000"]