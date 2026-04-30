# Clipper-Pro Operational Runbook

This document provides guidance for monitoring, troubleshooting, and maintaining the Clipper-Pro production pipeline.

## 1. Pipeline Observability

### Status Fields
- `status`: The current state of the job (`queued`, `processing`, `completed`, `error`).
- `status_message`: Informative progress updates (e.g., "Downloading video", "AI analysis in progress").
- `error_message`: Fatal error details if `status == 'error'`.

### Monitoring Logs (Google Cloud)
All services use structured JSON logging. You can filter logs in Log Explorer using:
```query
jsonPayload.correlation_id="YOUR_JOB_ID"
```
This will show all logs across Backend, GPU Worker, and Node Worker for a specific job.

## 2. Troubleshooting common issues

### Job stuck in 'WAITING' or 'QUEUED'
1. **Check Pub/Sub**: Ensure messages are arriving in `clipper-caption-jobs` topic.
2. **Check Worker Logs**: Look for "GPU Diagnostics failed" or connection errors.
3. **GPU Availability**: Verify that the GPU worker has an L4 GPU attached.

### GPU Performance issues
If rendering is slow or GPU utilization is low:
1. Check `run_gpu_diagnostics` output at worker startup.
2. Ensure `ffmpeg` is using `h264_nvenc`.
3. Verify that `torch.cuda.is_available()` is `True`.

### SSE Connection Drops
- The backend sends a `: ping` heartbeat every 2 seconds.
- If connections drop, check Cloud Run timeout settings (currently set to 3600s).

## 3. Deployment & Scaling

### Scaling GPU Workers
- GPU workers should have `containerConcurrency: 1`.
- Scale using Pub/Sub backlog metrics.

### Environment Variables
- `ENVIRONMENT`: Set to `production` for JSON logging.
- `STRICT_GPU_CHECK`: Set to `true` to force worker shutdown if GPU is not functional.
- `GCP_PROJECT_ID`: Required for Pub/Sub and Logging.

## 4. Emergency Procedures

### Clear Stale Jobs
If a job is stuck in `processing` for more than 10 minutes:
1. Another worker will automatically re-take ownership after 5 minutes of inactivity (idempotency check).
2. Or, manually update the status in Supabase/DB to `error` to allow retry.
