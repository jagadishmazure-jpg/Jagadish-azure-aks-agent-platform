# Multi-stage, non-root, read-only-friendly image for the claims agents.
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
RUN useradd --uid 10001 --create-home app
COPY --from=build /install /usr/local
USER 10001
ENV PYTHONUNBUFFERED=1 CHECKPOINT_DIR=/data/checkpoints
EXPOSE 8080
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["uvicorn", "nfclaims.app:app", "--host", "0.0.0.0", "--port", "8080"]
