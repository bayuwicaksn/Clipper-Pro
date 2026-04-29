# ── Stage 1: Build React ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --silent
COPY . .
RUN npm run build

# ── Stage 2: Serve dengan Nginx ───────────────────────────────────────
FROM nginx:1.25-alpine

# Pindahkan semua nginx write path ke /tmp (writable oleh non-root)
RUN sed -i 's|/var/run/nginx.pid|/tmp/nginx.pid|g' /etc/nginx/nginx.conf && \
    sed -i 's|/var/cache/nginx|/tmp/nginx_cache|g' /etc/nginx/nginx.conf && \
    # Buat direktori yang dibutuhkan nginx
    mkdir -p /tmp/nginx_cache \
    /tmp/client_temp \
    /tmp/proxy_temp \
    /tmp/fastcgi_temp \
    /tmp/uwsgi_temp \
    /tmp/scgi_temp && \
    # Berikan akses ke html directory
    chmod -R 755 /usr/share/nginx/html && \
    # Hapus default config
    rm /etc/nginx/conf.d/default.conf

# Copy build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Non-root user (nginx sudah ada di alpine)
USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]