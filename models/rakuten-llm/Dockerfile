FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch and other dependencies
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir transformers accelerate bitsandbytes sentencepiece fastapi uvicorn pydantic

# Clone the repository for OpenAI API compatibility
RUN git clone https://github.com/lm-sys/FastChat.git /app/FastChat
WORKDIR /app/FastChat
RUN pip install --no-cache-dir -e .

# Create model directory
RUN mkdir -p /app/models

# Copy the model serving script
COPY serve.py /app/

# Expose the port
EXPOSE 8000

# Start the server
CMD ["python", "/app/serve.py"]