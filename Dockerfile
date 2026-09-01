# Use official Playwright image with pre-installed browsers and OS dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=7860

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies list and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn

# Copy project files
COPY . .

# Ensure user data directory exists and has permissions
RUN mkdir -p /app/whatsapp_user_data && chmod -R 777 /app

# Expose Hugging Face Spaces port
EXPOSE 7860

# Start script running web dashboard and background monitoring
CMD ["python3", "app.py"]
