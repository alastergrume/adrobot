# Build context is the project root:
#   docker build -f docker/Dockerfile -t adrobot .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Run as an unprivileged user. The database is a docker-compose service (DATABASE_URL is set there).
RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

# Apply migrations, then start the server.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
