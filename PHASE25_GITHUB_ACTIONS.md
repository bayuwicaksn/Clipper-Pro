# Phase 2.5 — GitHub Actions CI/CD
## Instruksi untuk Coding Agent

---

## KONTEKS

Build lokal gagal karena disk penuh.
Solusi: Build semua Docker image di GitHub Actions, push ke GCP Artifact Registry,
lalu deploy ke Cloud Run.

Phase 2.5 ini membuat:
1. GitHub Actions workflow untuk build + push semua image
2. GCP Artifact Registry setup
3. Cloud Run deployment config (tanpa GPU dulu, untuk test)
4. Workflow trigger: setiap push ke branch `main`

**PENTING:**
- Jangan build Docker lokal lagi
- Semua build terjadi di GitHub Actions runner (disk 14GB)
- Image disimpan di GCP Artifact Registry, bukan Docker Hub

---

## RULES UNTUK AGENT

1. Kerjakan BERURUTAN
2. Jangan skip step GitHub Secrets — workflow tidak akan jalan tanpa ini
3. Setiap file YAML harus valid syntax — gunakan yaml lint jika ragu
4. Commit semua file sebelum push

---

## STEP 1 — Buat GCP Artifact Registry

Agent TIDAK perlu jalankan ini — instruksi untuk USER.
Tapi agent harus tahu nama registry yang digunakan.

Registry yang akan digunakan:
```
Format: REGION-docker.pkg.dev/PROJECT_ID/REPO_NAME/IMAGE_NAME
Contoh: asia-southeast1-docker.pkg.dev/my-project/clipper/frontend
```

User harus jalankan ini di GCP Console atau Cloud Shell:
```bash
# Buat repository di Artifact Registry
gcloud artifacts repositories create clipper \
  --repository-format=docker \
  --location=asia-southeast1 \
  --description="Clipper-Pro Docker images"

# Verify
gcloud artifacts repositories list --location=asia-southeast1
```

---

## STEP 2 — Buat GitHub Actions Workflow

Buat file `.github/workflows/deploy.yml`:

```yaml
name: Build & Deploy Clipper-Pro

on:
  push:
    branches:
      - main
  # Manual trigger
  workflow_dispatch:
    inputs:
      service:
        description: 'Service to deploy (all/frontend/backend/worker_gpu/worker_node)'
        required: false
        default: 'all'

# Env variables global
env:
  GCP_REGION: asia-southeast1
  REGISTRY: asia-southeast1-docker.pkg.dev
  REPO: clipper

jobs:

  # ── Job 1: Build & Push Frontend ─────────────────────────────────────
  build-frontend:
    name: Build Frontend
    runs-on: ubuntu-latest
    # Hanya build jika ada perubahan di frontend/ atau workflow berubah
    if: |
      github.event.inputs.service == 'all' ||
      github.event.inputs.service == 'frontend' ||
      github.event.inputs.service == ''

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Setup gcloud CLI
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: |
          gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Build & Push Frontend
        run: |
          IMAGE=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/frontend
          
          docker build \
            --tag $IMAGE:latest \
            --tag $IMAGE:${{ github.sha }} \
            --cache-from $IMAGE:latest \
            --file frontend/Dockerfile \
            frontend/
          
          docker push $IMAGE:latest
          docker push $IMAGE:${{ github.sha }}
          
          echo "IMAGE_FRONTEND=$IMAGE:${{ github.sha }}" >> $GITHUB_ENV

      - name: Deploy Frontend to Cloud Run
        run: |
          IMAGE=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/frontend
          
          gcloud run deploy clipper-frontend \
            --image $IMAGE:${{ github.sha }} \
            --region ${{ env.GCP_REGION }} \
            --platform managed \
            --allow-unauthenticated \
            --port 80 \
            --memory 512Mi \
            --cpu 1 \
            --min-instances 0 \
            --max-instances 5 \
            --set-env-vars "ENVIRONMENT=production"

  # ── Job 2: Build & Push Backend ──────────────────────────────────────
  build-backend:
    name: Build Backend
    runs-on: ubuntu-latest
    if: |
      github.event.inputs.service == 'all' ||
      github.event.inputs.service == 'backend' ||
      github.event.inputs.service == ''

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Setup gcloud CLI
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: |
          gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Build & Push Backend
        run: |
          IMAGE=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/backend
          
          docker build \
            --tag $IMAGE:latest \
            --tag $IMAGE:${{ github.sha }} \
            --cache-from $IMAGE:latest \
            --file backend/Dockerfile \
            --build-context shared=shared \
            backend/
          
          docker push $IMAGE:latest
          docker push $IMAGE:${{ github.sha }}

      - name: Deploy Backend to Cloud Run
        run: |
          IMAGE=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/backend
          
          gcloud run deploy clipper-backend \
            --image $IMAGE:${{ github.sha }} \
            --region ${{ env.GCP_REGION }} \
            --platform managed \
            --allow-unauthenticated \
            --port 8000 \
            --memory 1Gi \
            --cpu 2 \
            --min-instances 0 \
            --max-instances 10 \
            --set-env-vars "ENVIRONMENT=production" \
            --set-secrets "SUPABASE_URL=SUPABASE_URL:latest" \
            --set-secrets "SUPABASE_KEY=SUPABASE_KEY:latest" \
            --set-secrets "GCP_PROJECT_ID=GCP_PROJECT_ID:latest" \
            --set-secrets "PUBSUB_TOPIC_JOBS=PUBSUB_TOPIC_JOBS:latest"

  # ── Job 3: Build & Push Worker GPU ───────────────────────────────────
  build-worker-gpu:
    name: Build Worker GPU
    # Worker GPU image besar (~3GB) — butuh runner dengan disk lebih besar
    runs-on: ubuntu-latest
    if: |
      github.event.inputs.service == 'all' ||
      github.event.inputs.service == 'worker_gpu' ||
      github.event.inputs.service == ''

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Free disk space
        # Worker GPU image besar, perlu bebaskan disk dulu
        run: |
          echo "Disk before cleanup:"
          df -h
          
          # Hapus software yang tidak diperlukan
          sudo rm -rf /usr/share/dotnet
          sudo rm -rf /usr/local/lib/android
          sudo rm -rf /opt/ghc
          sudo rm -rf /opt/hostedtoolcache/CodeQL
          sudo docker image prune --all --force
          
          echo "Disk after cleanup:"
          df -h

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Setup gcloud CLI
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: |
          gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build & Push Worker GPU
        uses: docker/build-push-action@v5
        with:
          context: worker_gpu
          file: worker_gpu/Dockerfile
          push: true
          # Cache dari Artifact Registry (hemat waktu build ulang)
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-gpu:cache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-gpu:cache,mode=max
          tags: |
            ${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-gpu:latest
            ${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-gpu:${{ github.sha }}
          build-args: |
            WHISPER_MODEL=medium

      - name: Deploy Worker GPU to Cloud Run
        run: |
          IMAGE=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-gpu
          
          gcloud run deploy clipper-worker-gpu \
            --image $IMAGE:${{ github.sha }} \
            --region ${{ env.GCP_REGION }} \
            --platform managed \
            --no-allow-unauthenticated \
            --port 8080 \
            --memory 16Gi \
            --cpu 8 \
            --gpu 1 \
            --gpu-type nvidia-l4 \
            --min-instances 0 \
            --max-instances 3 \
            --timeout 3600 \
            --concurrency 1 \
            --set-env-vars "ENVIRONMENT=production,WHISPER_MODEL=medium,GPU_ENABLED=true" \
            --set-secrets "GCP_PROJECT_ID=GCP_PROJECT_ID:latest" \
            --set-secrets "PUBSUB_SUBSCRIPTION_JOBS=PUBSUB_SUBSCRIPTION_JOBS:latest" \
            --set-secrets "GCS_BUCKET=GCS_BUCKET:latest" \
            --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest" \
            --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest"

  # ── Job 4: Build & Push Worker Node ──────────────────────────────────
  build-worker-node:
    name: Build Worker Node
    runs-on: ubuntu-latest
    if: |
      github.event.inputs.service == 'all' ||
      github.event.inputs.service == 'worker_node' ||
      github.event.inputs.service == ''

    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Free disk space
        run: |
          sudo rm -rf /usr/share/dotnet
          sudo rm -rf /usr/local/lib/android
          sudo docker image prune --all --force
          df -h

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Setup gcloud CLI
        uses: google-github-actions/setup-gcloud@v2

      - name: Configure Docker for Artifact Registry
        run: |
          gcloud auth configure-docker ${{ env.REGISTRY }} --quiet

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build & Push Worker Node
        uses: docker/build-push-action@v5
        with:
          context: worker_node
          file: worker_node/Dockerfile
          push: true
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-node:cache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-node:cache,mode=max
          tags: |
            ${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-node:latest
            ${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-node:${{ github.sha }}

      - name: Deploy Worker Node to Cloud Run
        run: |
          IMAGE=${{ env.REGISTRY }}/${{ secrets.GCP_PROJECT_ID }}/${{ env.REPO }}/worker-node
          
          gcloud run deploy clipper-worker-node \
            --image $IMAGE:${{ github.sha }} \
            --region ${{ env.GCP_REGION }} \
            --platform managed \
            --no-allow-unauthenticated \
            --port 8080 \
            --memory 4Gi \
            --cpu 4 \
            --min-instances 0 \
            --max-instances 5 \
            --timeout 1800 \
            --concurrency 1 \
            --set-env-vars "ENVIRONMENT=production" \
            --set-secrets "GCP_PROJECT_ID=GCP_PROJECT_ID:latest" \
            --set-secrets "PUBSUB_SUBSCRIPTION_CAPTION=PUBSUB_SUBSCRIPTION_CAPTION:latest" \
            --set-secrets "GCS_BUCKET=GCS_BUCKET:latest"

  # ── Job 5: Notify setelah semua selesai ──────────────────────────────
  notify:
    name: Deployment Summary
    runs-on: ubuntu-latest
    needs: [build-frontend, build-backend, build-worker-gpu, build-worker-node]
    if: always()

    steps:
      - name: Summary
        run: |
          echo "## Deployment Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Service | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|---------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Frontend | ${{ needs.build-frontend.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Backend | ${{ needs.build-backend.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Worker GPU | ${{ needs.build-worker-gpu.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Worker Node | ${{ needs.build-worker-node.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "Commit: ${{ github.sha }}" >> $GITHUB_STEP_SUMMARY
          echo "Triggered by: ${{ github.actor }}" >> $GITHUB_STEP_SUMMARY
```

VERIFY syntax:
```bash
# Install yaml lint jika belum ada
pip install yamllint
yamllint .github/workflows/deploy.yml
```

---

## STEP 3 — Buat Workflow Khusus untuk Test (Tanpa Deploy)

Buat file `.github/workflows/test-build.yml`:

```yaml
name: Test Build Only (No Deploy)

on:
  pull_request:
    branches:
      - main
  # Manual trigger untuk test build saja
  workflow_dispatch:

env:
  GCP_REGION: asia-southeast1
  REGISTRY: asia-southeast1-docker.pkg.dev
  REPO: clipper

jobs:

  test-build-frontend:
    name: Test Build Frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Frontend (no push)
        run: |
          docker build \
            --file frontend/Dockerfile \
            frontend/
          echo "✅ Frontend build OK"

  test-build-backend:
    name: Test Build Backend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Backend (no push)
        run: |
          docker build \
            --file backend/Dockerfile \
            backend/
          echo "✅ Backend build OK"

  test-build-worker-gpu:
    name: Test Build Worker GPU
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Free disk space
        run: |
          sudo rm -rf /usr/share/dotnet
          sudo rm -rf /usr/local/lib/android
          sudo docker image prune --all --force
          df -h

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Worker GPU (no push)
        uses: docker/build-push-action@v5
        with:
          context: worker_gpu
          file: worker_gpu/Dockerfile
          push: false
          build-args: |
            WHISPER_MODEL=medium

  test-build-worker-node:
    name: Test Build Worker Node
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Free disk space
        run: |
          sudo rm -rf /usr/share/dotnet
          sudo rm -rf /usr/local/lib/android
          sudo docker image prune --all --force

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Worker Node (no push)
        uses: docker/build-push-action@v5
        with:
          context: worker_node
          file: worker_node/Dockerfile
          push: false
```

---

## STEP 4 — Update Dockerfile untuk Support --build-context shared

Karena GitHub Actions build dari context folder masing-masing,
`COPY ../shared` tidak akan work. Perlu diupdate semua Dockerfile.

### Update backend/Dockerfile
Cari baris:
```dockerfile
COPY ../shared /app/shared
```
Ganti dengan:
```dockerfile
# shared di-inject via --build-context saat build
# Jika tidak ada, skip (tidak required untuk backend minimal)
COPY --from=shared . /app/shared/
```

### Update worker_gpu/Dockerfile
Cari baris:
```dockerfile
COPY ../shared /app/shared
```
Ganti dengan:
```dockerfile
COPY --from=shared . /app/shared/
```

### Update worker_node/Dockerfile
Cari baris:
```dockerfile
COPY ../shared /app/shared
```
Ganti dengan:
```dockerfile
COPY --from=shared . /app/shared/
```

CATATAN: `--build-context shared=shared` sudah ada di workflow deploy.yml step backend.
Untuk worker_gpu dan worker_node, tambahkan juga di workflow:

Di `.github/workflows/deploy.yml`, update step Build Worker GPU:
```yaml
      - name: Build & Push Worker GPU
        uses: docker/build-push-action@v5
        with:
          context: worker_gpu
          file: worker_gpu/Dockerfile
          push: true
          # TAMBAHKAN baris ini:
          build-contexts: |
            shared=shared
```

Lakukan hal sama untuk Build Worker Node.

---

## STEP 5 — Setup GitHub Secrets

Agent TIDAK bisa setup secrets — ini harus dilakukan USER secara manual.

Buat file `SECRETS_SETUP.md` di root sebagai reminder untuk user:

```markdown
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
```

---

## STEP 6 — Commit dan Push

```bash
# Dari root repo
git add .github/workflows/deploy.yml
git add .github/workflows/test-build.yml
git add SECRETS_SETUP.md
git add frontend/Dockerfile
git add frontend/nginx.conf
git add backend/Dockerfile
git add backend/main.py
git add worker_gpu/Dockerfile
git add worker_gpu/worker.py
git add worker_node/Dockerfile
git add worker_node/worker.py

# Commit
git commit -m "feat: add GitHub Actions CI/CD + Dockerfiles (Phase 2.5)"

# Push ke main
git push origin main
```

Setelah push, buka:
`https://github.com/bayuwicaksn/Clipper-Pro/actions`

Dan pantau workflow berjalan.

---

## STEP 7 — Strategi Build Bertahap

Supaya tidak semua build jalan sekaligus (hemat quota Actions),
gunakan manual trigger dengan memilih service:

```
Urutan yang direkomendasikan:
1. Deploy frontend dulu (paling cepat, ~3 menit)
2. Deploy backend (~5 menit)
3. Deploy worker_node (~8 menit)
4. Deploy worker_gpu TERAKHIR (~15-20 menit, paling berat)
```

Cara trigger manual satu service:
```
GitHub → Actions → Build & Deploy Clipper-Pro
→ Run workflow → pilih service: frontend
→ Run workflow
```

---

## CHECKLIST FINAL UNTUK AGENT

```
[ ] .github/workflows/deploy.yml ada dan valid YAML
[ ] .github/workflows/test-build.yml ada dan valid YAML
[ ] SECRETS_SETUP.md ada
[ ] Semua Dockerfile diupdate (hapus COPY ../shared, pakai --from=shared)
[ ] deploy.yml punya build-contexts untuk semua worker
[ ] git add semua file baru
[ ] git commit berhasil
[ ] git push ke main berhasil
[ ] GitHub Actions tab menunjukkan workflow berjalan
[ ] PHASE25_DONE.md dibuat
```

---

## JIKA ADA ERROR DI GITHUB ACTIONS

### Error: "Permission denied to Artifact Registry"
```
Solusi: Pastikan GCP_SA_KEY punya role artifactregistry.writer
Check: GCP Console → IAM → cari service account → edit roles
```

### Error: "No space left on device" di GitHub runner
```
Solusi: Sudah ada step "Free disk space" di workflow
Jika masih error, tambahkan:
  sudo apt-get clean
  sudo rm -rf /tmp/*
```

### Error: "COPY --from=shared: not found"
```
Solusi: Pastikan build-contexts sudah ditambahkan di workflow:
  build-contexts: |
    shared=shared
```

### Error: "Cloud Run GPU not available"
```
Solusi: GPU L4 hanya tersedia di region tertentu
Pastikan region: us-central1 atau asia-southeast1
Atau hapus --gpu flag dulu untuk test tanpa GPU
```

### Error: "Secret not found"
```
Solusi: Pastikan semua secrets sudah ditambahkan di GitHub
Settings → Secrets → Actions → pastikan nama exact sama
```

---

## PHASE 2.5 DONE

Buat file `PHASE25_DONE.md`:

```markdown
# Phase 2.5 Complete

## Yang sudah dikerjakan:
- [x] .github/workflows/deploy.yml (build + push + deploy semua service)
- [x] .github/workflows/test-build.yml (test build tanpa deploy)
- [x] SECRETS_SETUP.md (panduan setup secrets untuk user)
- [x] Semua Dockerfile diupdate untuk support --build-context shared
- [x] Semua file di-commit dan push ke main

## Yang harus dilakukan USER (bukan agent):
- [ ] Setup GCP Service Account + download JSON key
- [ ] Tambahkan semua GitHub Secrets
- [ ] Buat Artifact Registry di GCP
- [ ] Buat Cloud Storage bucket
- [ ] Buat Pub/Sub topics + subscriptions
- [ ] Trigger workflow manual per service

## Next: Phase 3
- Implementasi worker_gpu/tasks/ (download, transcribe, analyze, clip)
- Implementasi worker_node tasks penuh
- Pub/Sub integration penuh
- Hapus file lama (core/, api/, services/, app.py root)
```

---

**END OF PHASE 2.5 INSTRUCTIONS**
