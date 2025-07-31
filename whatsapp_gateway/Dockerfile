# Use an official Python runtime as a parent image
FROM python:3.11.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container to /app for consistency
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies into a virtual environment for isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./src ./src
COPY ./migrations ./migrations
COPY ./entrypoint.sh .
RUN chmod +x ./entrypoint.sh

# Create a non-root user for security
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=src.main

# Expose the port the app runs on
EXPOSE 5000

# Run the entrypoint script which will then execute the CMD
ENTRYPOINT ["./entrypoint.sh"]

# The default command to start the application with Hypercorn
CMD ["hypercorn", "src.main:app", "--bind", "0.0.0.0:5000"]