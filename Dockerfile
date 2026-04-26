# syntax=docker/dockerfile:1

FROM --platform=$BUILDPLATFORM node:22-alpine3.20 AS frontend

ARG BUILD_HASH=dev-build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --force

COPY . .
ENV APP_BUILD_HASH=${BUILD_HASH}
ENV NODE_OPTIONS=--max-old-space-size=8192
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

ARG BUILD_HASH=dev-build
ARG UID=0
ARG GID=0

ENV ENV=prod \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    WEBUI_BUILD_VERSION=${BUILD_HASH} \
    DOCKER=true \
    ENABLE_OLLAMA_API=false \
    ENABLE_CHANNELS=false \
    ENABLE_NOTES=false \
    ENABLE_CALENDAR=false \
    ENABLE_WEB_SEARCH=false \
    ENABLE_CODE_EXECUTION=false \
    ENABLE_CODE_INTERPRETER=false \
    ENABLE_IMAGE_GENERATION=false \
    VECTOR_DB=none \
    HERMES_API_BASE_URL=http://host.docker.internal:8642 \
    OPENAI_API_BASE_URL=http://host.docker.internal:8642 \
    OPENAI_API_KEY="" \
    WEBUI_SECRET_KEY="" \
    SCARF_NO_ANALYTICS=true \
    DO_NOT_TRACK=true \
    ANONYMIZED_TELEMETRY=false

WORKDIR /app/backend

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl jq ffmpeg netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY --chown=$UID:$GID backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir uv && \
    uv pip install --system -r requirements.txt --no-cache-dir

COPY --chown=$UID:$GID --from=frontend /app/build /app/build
COPY --chown=$UID:$GID --from=frontend /app/package.json /app/package.json
COPY --chown=$UID:$GID backend .

RUN mkdir -p /app/backend/data && chown -R $UID:$GID /app /app/backend/data

USER $UID:$GID
EXPOSE 8080

HEALTHCHECK CMD curl --silent --fail http://localhost:${PORT}/health | jq -ne 'input.status == true' || exit 1

CMD ["bash", "start.sh"]
