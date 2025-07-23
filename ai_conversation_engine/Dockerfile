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

# Copy the Gunicorn configuration file to the container
COPY gunicorn.conf.py /app

# REMOVED: Do not copy the .env file into the image for security
# COPY .env /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security
RUN useradd -m -u 1000 appuser

# Give the new user ownership of the app directory
RUN chown -R appuser:appuser /app

# Set the Python path environment variable
ENV PYTHONPATH=/app

# Set the Flask application entry point
ENV FLASK_APP=src.main

# Make port 5001 available to the world outside this container
EXPOSE 5001

# Switch to the non-root user
USER appuser

# Define the command to run the application using a Gunicorn config file
CMD ["gunicorn", "--config", "./gunicorn.conf.py", "src.main:app"]