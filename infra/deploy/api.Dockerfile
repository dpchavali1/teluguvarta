# API + worker image (same image, different command). Build context = repo root.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
# Layout mirrors the repo: alembic.ini resolves ../../infra/migrations and
# seed.py resolves apps/api relative to itself.
# Dependencies come only from the hashed lock (review #17); the package
# itself is installed with --no-deps so nothing unpinned slips in.
COPY apps/api/requirements.lock apps/api/
RUN pip install --require-hashes -r apps/api/requirements.lock
COPY apps/api/pyproject.toml apps/api/alembic.ini apps/api/
COPY apps/api/app apps/api/app
COPY infra/migrations infra/migrations
COPY infra/scripts infra/scripts
RUN pip install --no-deps ./apps/api
WORKDIR /srv/apps/api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
