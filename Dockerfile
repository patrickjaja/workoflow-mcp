FROM python:3.12-slim

WORKDIR /app

# Copy package files
COPY pyproject.toml .
COPY src/ ./src/

# Install package with dependencies
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 9000

# Health check - verify server is listening
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('localhost',9000)); s.close()" || exit 1

# Run the server
CMD ["fastmcp", "run", "src/workoflow_mcp/server.py:mcp", "--transport", "http", "--host", "0.0.0.0", "--port", "9000"]
