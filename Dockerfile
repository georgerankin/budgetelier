FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy dependency list first (Docker layer caching: only re-installs if this file changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make the startup script executable
RUN chmod +x start.sh

# Flask app runs on this port
EXPOSE 5000

# Seed the database with schema + demo data, then start gunicorn
CMD ["./start.sh"]