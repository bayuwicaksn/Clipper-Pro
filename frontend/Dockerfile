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

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
