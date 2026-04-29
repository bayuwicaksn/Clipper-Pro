# GitHub Secrets Setup

Buka: https://github.com/bayuwicaksn/Clipper-Pro/settings/secrets/actions

Tambahkan secrets berikut (klik "New repository secret"):

## Required Secrets

| Secret Name | Value | Cara Dapat |
|-------------|-------|------------|
| `GCP_SA_KEY` | JSON key GCP Service Account | GCP Console → IAM → Service Accounts → Keys |
| `GCP_PROJECT_ID` | ID project GCP kamu | GCP Console → Dashboard |
| `SUPABASE_URL` | URL Supabase project | Supabase → Settings → API |
| `SUPABASE_KEY` | Anon key Supabase | Supabase → Settings → API |
| `GEMINI_API_KEY` | Gemini API key | Google AI Studio |
| `OPENAI_API_KEY` | OpenAI API key (opsional) | platform.openai.com |
| `GCS_BUCKET` | Nama bucket Cloud Storage | GCP Console → Cloud Storage |
| `PUBSUB_TOPIC_JOBS` | Nama topic Pub/Sub jobs | `clipper-jobs` |
| `PUBSUB_SUBSCRIPTION_JOBS` | Nama subscription | `clipper-jobs-sub` |
| `PUBSUB_TOPIC_CAPTION` | Nama topic caption | `clipper-caption-jobs` |
| `PUBSUB_SUBSCRIPTION_CAPTION` | Nama subscription caption | `clipper-caption-jobs-sub` |

## GCP Service Account Permissions

Service account yang di-download harus punya roles:
- `roles/artifactregistry.writer`
- `roles/run.admin`
- `roles/storage.admin`
- `roles/pubsub.admin`
- `roles/iam.serviceAccountUser`
- `roles/secretmanager.secretAccessor`

## Cara Buat Service Account

1. Buka GCP Console → IAM & Admin → Service Accounts
2. Klik "Create Service Account"
3. Nama: `clipper-pro-deployer`
4. Tambahkan semua roles di atas
5. Klik "Keys" → "Add Key" → "JSON"
6. Download file JSON
7. Copy isi file JSON ke GitHub Secret `GCP_SA_KEY`
