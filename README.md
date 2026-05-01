# Clipper-Pro

Clipper-Pro is split into a React frontend, FastAPI backend, GPU worker, Node/Chromium caption worker, shared utilities, and deployment infra.

Main flow:

1. Frontend calls `POST /api/pipeline/start`.
2. Backend creates a job and publishes to the jobs Pub/Sub topic.
3. `worker_gpu` downloads, transcribes, analyzes, clips, and queues caption jobs.
4. `worker_node` renders captions, composites final video, uploads output, and updates status.
5. Frontend receives progress through SSE.

## Deployment
Clipper-Pro is automatically deployed to Google Cloud Run via GitHub Actions.

### Setup
Ensure the following GitHub Secrets are set:
- `GCP_PROJECT_ID`: Your Google Cloud Project ID.
- `GCP_SA_KEY`: JSON key for a Service Account with Cloud Run Admin and Pub/Sub Admin roles.
- `GCP_SA_EMAIL`: The email of the same Service Account (used for Pub/Sub push auth).
- `DATABASE_URL`: Supabase PostgreSQL connection string.
- `GCS_BUCKET`: Google Cloud Storage bucket name.
- `GEMINI_API_KEY`, `OPENAI_API_KEY`: AI provider keys.
- `SUPABASE_URL`, `SUPABASE_KEY`: Supabase project credentials.

### Infrastructure Note
The deployment pipeline automatically configures Pub/Sub topics and **Push Subscriptions**. 
On the **very first deployment** to a new project, the pipeline might create Pull subscriptions initially as a fallback. The automated `configure-push-subs` job will then attempt to convert them to Push once the workers are live. If you encounter any "no response" issues on a brand new project, simply trigger the deployment workflow a second time or manually verify the Push settings in the GCP Console.
