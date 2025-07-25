# Use a specific version of Python for stability
FROM python:3.11.9-slim

# Install system dependencies needed for both building and running
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and set up the working directory
RUN useradd -m -u 1000 appuser
WORKDIR /home/appuser
USER appuser

# Set up the Python virtual environment
ENV PATH="/home/appuser/venv/bin:$PATH"
RUN python -m venv /home/appuser/venv

# Copy requirements first to leverage Docker's build cache
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY --chown=appuser:appuser ./src ./src
COPY --chown=appuser:appuser ./migrations ./migrations
COPY --chown=appuser:appuser ./entrypoint.sh .
RUN chmod +x ./entrypoint.sh

# Expose the port the application will run on
EXPOSE 5000

# Set the entrypoint to start the application
ENTRYPOINT ["./entrypoint.sh"]

# The default command to start the application with Hypercorn
CMD ["python", "-m", "hypercorn", "src.main:app", "--bind", "0.0.0.0:5000"]