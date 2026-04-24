# ═══════════════════════════════════════════════════════════
# ClipperApp — Budget-Optimized GCP Schedule Scripts
# 
# Auto start/stop VM to save money:
#   VM only runs when you need it (~12 hours/day)
#   Saves ~50% on compute costs!
# ═══════════════════════════════════════════════════════════

# ─── Option 1: Manual start/stop from your local PC ──────

# Start VM when you begin working
gcloud compute instances start clipperapp --zone=us-central1-a --quiet

# Stop VM when done (IMPORTANT! Saves ~$15/month)
gcloud compute instances stop clipperapp --zone=us-central1-a --quiet

# ─── Option 2: Auto-schedule via Cloud Scheduler ─────────
# Start at 8 AM WIB (1 AM UTC), Stop at 11 PM WIB (4 PM UTC)

# Create start schedule
gcloud scheduler jobs create http clipperapp-start \
    --schedule="0 1 * * *" \
    --uri="https://compute.googleapis.com/compute/v1/projects/YOUR_PROJECT/zones/us-central1-a/instances/clipperapp/start" \
    --http-method=POST \
    --oauth-service-account-email=YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com \
    --time-zone="Asia/Jakarta" \
    --quiet

# Create stop schedule
gcloud scheduler jobs create http clipperapp-stop \
    --schedule="0 16 * * *" \
    --uri="https://compute.googleapis.com/compute/v1/projects/YOUR_PROJECT/zones/us-central1-a/instances/clipperapp/stop" \
    --http-method=POST \
    --oauth-service-account-email=YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com \
    --time-zone="Asia/Jakarta" \
    --quiet

# ─── Cost comparison ─────────────────────────────────────
# 24/7:    730 hours × $0.042 = $30.66/month
# 15hr/day: 450 hours × $0.042 = $18.90/month  (save $12)
# 12hr/day: 360 hours × $0.042 = $15.12/month  (save $15)
# On-demand: varies, potentially much less
