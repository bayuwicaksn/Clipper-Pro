FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --silent
COPY . .
RUN npm run build

# Stage 2: Serve static files dengan 'serve'
FROM node:20-alpine
RUN npm install -g serve
WORKDIR /app
COPY --from=builder /app/dist ./dist

EXPOSE 8080

# 'serve' otomatis baca PORT env var dari Cloud Run
CMD ["serve", "-s", "dist", "-l", "8080"]