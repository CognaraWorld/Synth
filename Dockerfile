# Synth backend — production container image.
#
# Multi-stage: a `deps` stage installs Python deps into a venv, and the
# final stage copies only the venv + app code. This keeps the image small
# and avoids shipping build toolchains to production.

FROM python:3.12-slim-bookworm AS deps

# Build-only packages we need for wheels that don't publish manylinux
# binaries (e.g. some audio / crypto libs). Kept out of the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libffi-dev \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Isolate deps in a venv so the final stage can just copy one directory.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt


# -----------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Runtime-only packages. ffmpeg is required for Recall.ai audio conversion
# (pydub uses it for the PCM→MP3 path) and for some document export paths.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        libsndfile1 \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 synth \
    && useradd --system --uid 1000 --gid synth --home /app --shell /usr/sbin/nologin synth

COPY --from=deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TOKENIZERS_PARALLELISM=false \
    ENVIRONMENT=production

WORKDIR /app

# Copy the app after deps so dep changes don't invalidate the code layer.
COPY --chown=synth:synth backend/app ./app

# Writable state dirs. Mount volumes over these in production.
RUN mkdir -p /app/uploads /app/summaries /app/chroma_data \
    && chown -R synth:synth /app

USER synth

EXPOSE 8000

# tini reaps zombie children correctly. uvicorn stays as PID-ish (1.x).
# Workers are pinned to 1 because BotEngine and its session state are
# single-process (Redis/engine-singleton rework is tracked separately).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
