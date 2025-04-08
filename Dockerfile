FROM python:3.12-slim

WORKDIR /app

# Install Redis
RUN apt-get update && apt-get install -y redis-server

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directory for API keys
RUN mkdir -p /app/data

# Set environment variables
ENV PORT=8080
ENV API_KEYS_FILE=/app/data/api_keys.json
ENV ENABLE_CACHING=true
ENV CACHE_TTL=3600
ENV MAX_TOKENS_PER_REQUEST=4000

# Expose the port
EXPOSE 8080

# Create startup script
RUN echo '#!/bin/bash\n\
# Start Redis server\n\
redis-server --daemonize yes\n\
\n\
# Wait for Redis to start\n\
sleep 2\n\
\n\
# Run the application\n\
exec uvicorn main:app --host 0.0.0.0 --port 8080\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]