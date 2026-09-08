# Moxie Taste API (reference-council) — container for Coolify.
#
# Build context is the repo root so both moxie-api/ (the FastAPI app) and
# moxie-taste/ (the skill files that ARE the prompt) get copied while keeping
# the layout main.py expects: ROOT = <app>/.. , SKILL_DIR = ROOT/moxie-taste.
#
# Runtime env vars to set in Coolify (never bake these into the image):
#   GEMINI_API_KEY   required — the Gemini key
#   GEMINI_MODEL     the model id (defaults to gemini-2.5-flash if unset)
#   APIFY_API_KEY    only needed for /brief download=true (reel fetching)
#   PORT             optional — the port to listen on (defaults to 8000)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg + ffprobe drive the reel analysis; curl is for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Deps first for layer caching — only re-installs when requirements change.
COPY moxie-api/requirements.txt ./moxie-api/requirements.txt
RUN pip install --upgrade pip && pip install -r moxie-api/requirements.txt

# App + skill files, preserving the two-dir layout main.py resolves against.
COPY moxie-api ./moxie-api
COPY moxie-taste ./moxie-taste

# Reels land here (download=true writes them; GET /reel serves them). Mount a
# Coolify persistent volume at /app/reels so they survive restarts.
RUN mkdir -p /app/reels \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
VOLUME ["/app/reels"]

WORKDIR /app/moxie-api
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD sh -c 'curl -fsS "http://localhost:${PORT:-8000}/health" || exit 1'

# main.py reads PORT after load_dotenv, so a real env var (Coolify) or a PORT=
# line in .env both work.
CMD ["python", "main.py"]
