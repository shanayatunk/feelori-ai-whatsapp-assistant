# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies, including those needed for psycopg2
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the source code to the container
COPY ./src /app/src

# Copy the requirements file to the container
COPY requirements.txt /app

# REMOVED: Do not copy the .env file into the image for security
# COPY .env /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --timeout=600 -r requirements.txt

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Give the new user ownership of the app directory
RUN chown -R appuser:appuser /app

# Set the Flask application entry point
ENV FLASK_APP=src.main

# Set the Python path environment variable
ENV PYTHONPATH=/app

# Make port 5002 available to the world outside this container
EXPOSE 5002

# Switch to the non-root user
USER appuser

# Define the command to run the application using Hypercorn
CMD ["hypercorn", "src.main:app", "--bind", "0.0.0.0:5002"]