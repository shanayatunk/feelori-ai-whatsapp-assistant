# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies, including those needed for packages like psycopg2
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the source code to the container
COPY ./src /app/src

# Copy the requirements file to the container
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
# MODIFIED: Added --retries and --default-timeout to make the installation more resilient to network issues.
RUN pip install --no-cache-dir --timeout=600 --retries 10 --default-timeout 100 -r requirements.txt

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Give the new user ownership of the app directory
RUN chown -R appuser:appuser /app

# Set the Python path environment variable
ENV PYTHONPATH=/app/shared:/app/src

# Set the Flask application entry point
ENV FLASK_APP=src.main

# Make port 5001 available to the world outside this container
EXPOSE 5001

# Switch to the non-root user
USER appuser

# Add Docker HEALTHCHECK instruction
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl --fail http://localhost:5001/health || exit 1

# Define the command to run the application using Hypercorn
CMD ["hypercorn", "src.main:app", "--bind", "0.0.0.0:5001"]
