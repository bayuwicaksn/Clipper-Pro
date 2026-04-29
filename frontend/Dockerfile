# ── Stage 1: Build React ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files dulu (layer caching)
COPY package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy source
COPY . .

# Build production
# Vite output ke dist/, CRA output ke build/
RUN npm run build

# ── Stage 2: Serve dengan Nginx ───────────────────────────────────────
FROM nginx:1.25-alpine

# Copy build output
# Vite: dist/ | CRA: build/
# Ganti 'dist' dengan 'build' jika pakai Create React App
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config as a template
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Cloud Run set PORT env var — nginx alpine image has envsubst built-in
ENV PORT=8080
EXPOSE 8080

# Health check (listen to $PORT)
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --quiet --tries=1 --spider http://localhost:$PORT/ || exit 1

# Replace $PORT in template and start nginx
CMD ["/bin/sh", "-c", "envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
