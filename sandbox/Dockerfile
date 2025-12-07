# Sandbox Code Executor Service
# Lightweight FastAPI server for isolated code execution

FROM python:3.11-slim

# Minimal dependencies
RUN pip install --no-cache-dir fastapi uvicorn

# Create non-root user for security
RUN useradd -m -s /bin/bash sandbox && \
    mkdir -p /workspace && \
    chown sandbox:sandbox /workspace

WORKDIR /app

# Copy sandbox server code
COPY sandbox_server.py /app/sandbox_server.py

# Switch to non-root user
USER sandbox

# Expose port
EXPOSE 8001

# Run server
CMD ["uvicorn", "sandbox_server:app", "--host", "0.0.0.0", "--port", "8001"]
