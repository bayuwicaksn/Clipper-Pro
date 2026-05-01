#!/bin/bash
echo "[Entrypoint] Starting PO Token generation HTTP server..."
node /app/bgutil-ytdlp-pot-provider/server/build/main.js -p 4416 &

echo "[Entrypoint] Starting Python GPU worker..."
exec python3 worker.py
