FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# Copy application source code
COPY app/ ./app
# Hackathon deployment profile: use the private local .env when it is present
# in the source build context. Git builds without it retain safe defaults.
COPY .env* ./
RUN if [ ! -f .env ]; then cp .env.example .env; fi

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
