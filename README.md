# Clipper-Pro

Clipper-Pro is split into a React frontend, FastAPI backend, GPU worker, Node/Chromium caption worker, shared utilities, and deployment infra.

Main flow:

1. Frontend calls `POST /api/pipeline/start`.
2. Backend creates a job and publishes to the jobs Pub/Sub topic.
3. `worker_gpu` downloads, transcribes, analyzes, clips, and queues caption jobs.
4. `worker_node` renders captions, composites final video, uploads output, and updates status.
5. Frontend receives progress through SSE.
