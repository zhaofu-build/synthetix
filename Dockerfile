# ── Stage 1: Builder ──────────────────────────────────────────
# Install Node.js, build the frontend, then discard everything else.
FROM node:20-slim AS builder

WORKDIR /build/synthetix-vue

# Install npm dependencies first (layer cache)
COPY synthetix-vue/package.json synthetix-vue/package-lock.json* ./
RUN npm install

# Copy frontend source and build
COPY synthetix-vue/ .
RUN npm run build

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:3.11-slim

# Install only runtime system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY . .

# Copy built frontend from builder stage (overwrites the source copy)
COPY --from=builder /build/synthetix-vue/dist ./synthetix-vue/dist

# Create data directories with correct ownership
RUN mkdir -p /app/src/db /app/static && \
    chown -R app:app /app/src/db /app/static

# Database and media directories
VOLUME ["/app/src/db", "/app/static"]

EXPOSE 9527

# Run as non-root user
USER app

CMD ["python", "main.py"]
