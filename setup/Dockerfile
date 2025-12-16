FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests

# Copy setup scripts
COPY setup/setup_elasticsearch.py .
COPY setup/setup_rabbitmq_bindings.py .

# Copy templates
COPY elasticsearch/templates ./elasticsearch/templates

CMD ["python", "setup_elasticsearch.py"]
