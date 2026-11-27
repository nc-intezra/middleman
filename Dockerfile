FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml ./
COPY src ./src
COPY adapters ./adapters
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["uvicorn", "shim.main:app", "--host", "0.0.0.0", "--port", "8080"]
