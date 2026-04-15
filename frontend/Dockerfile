# syntax=docker/dockerfile:1.7

# ============================================================================
# AgenticFlow frontend — multistage image (node-builder → nginx)
# ============================================================================
# - builder: installs deps with `npm ci` and runs `npm run build`.
# - runtime: nginx:alpine serving the static bundle with SPA-style fallback
#   to /index.html and reverse-proxying /api + /metrics + /health to the
#   backend service (hostname resolved via docker-compose network DNS).
# ============================================================================

# --- builder ---------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Install deps with exact versions from package-lock.json
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# Tailwind + vite build, TypeScript type-check included via `npm run build`
RUN npm run build


# --- runtime ---------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Drop the default server block so ours isn't shadowed.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/agenticflow.conf

# Static assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Sensible cache headers already baked into nginx.conf.
EXPOSE 80

# nginx:alpine has its own ENTRYPOINT/CMD that runs nginx in foreground.

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
