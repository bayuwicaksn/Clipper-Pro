#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# ClipperApp — GCP Infrastructure Provisioning Script
#
# Creates a budget-optimized GCP setup:
#   - e2-medium VM (cheapest general purpose: ~$31/month)
#   - 30 GB SSD boot disk
#   - Firewall rules for HTTP/HTTPS
#   - Cloud Storage bucket for backups (optional)
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - A GCP project with billing enabled (trial works!)
#
# Usage:
#   bash deploy/gcp/provision.sh
# ═══════════════════════════════════════════════════════════════════

set -e

# ─── Configuration ────────────────────────────────────────
# EDIT THESE VALUES
PROJECT_ID=""           # Your GCP project ID (leave empty to use current)
REGION="us-central1"    # Cheapest region
ZONE="us-central1-a"
VM_NAME="clipperapp"
MACHINE_TYPE="e2-medium"  # 2 vCPU, 4 GB RAM — $0.042/hr = ~$31/month
DISK_SIZE="50"            # GB (SSD), ~$8.50/month
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

# ─── Preflight Checks ────────────────────────────────────
echo "╔═══════════════════════════════════════════════════╗"
echo "║   ClipperApp — GCP Provisioning                  ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# Use current project if not specified
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi

if [ -z "$PROJECT_ID" ]; then
    echo "❌ No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📋 Configuration:"
echo "   Project:  ${PROJECT_ID}"
echo "   Region:   ${REGION}"
echo "   Zone:     ${ZONE}"
echo "   VM:       ${MACHINE_TYPE} (${DISK_SIZE}GB SSD)"
echo ""

# ─── Budget Estimate ─────────────────────────────────────
echo "💰 Estimated Monthly Cost:"
echo "   ┌──────────────────────────────────┐"
echo "   │ VM (e2-medium, 24/7):   ~\$31.00 │"
echo "   │ Disk (50GB SSD):         ~\$8.50 │"
echo "   │ Egress (~20GB):          ~\$2.40 │"
echo "   │ ─────────────────────────────── │"
echo "   │ TOTAL:                  ~\$41.90 │"
echo "   │                                  │"
echo "   │ With \$300 trial = ~7 months!     │"
echo "   └──────────────────────────────────┘"
echo ""
read -p "Proceed? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then exit 1; fi

# ─── Enable Required APIs ─────────────────────────────────
echo ""
echo "🔧 [1/4] Enabling GCP APIs..."
gcloud services enable compute.googleapis.com --project=${PROJECT_ID} --quiet
echo "   ✅ Compute Engine API enabled"

# ─── Firewall Rules ──────────────────────────────────────
echo ""
echo "🔥 [2/4] Configuring firewall..."

# Allow HTTP (80)
gcloud compute firewall-rules create allow-http \
    --project=${PROJECT_ID} \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:80 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=http-server \
    --quiet 2>/dev/null || echo "   (http rule already exists)"

# Allow HTTPS (443)
gcloud compute firewall-rules create allow-https \
    --project=${PROJECT_ID} \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:443 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=https-server \
    --quiet 2>/dev/null || echo "   (https rule already exists)"

echo "   ✅ Firewall configured"

# ─── Create VM ───────────────────────────────────────────
echo ""
echo "🖥️  [3/4] Creating VM instance..."

gcloud compute instances create ${VM_NAME} \
    --project=${PROJECT_ID} \
    --zone=${ZONE} \
    --machine-type=${MACHINE_TYPE} \
    --image-family=${IMAGE_FAMILY} \
    --image-project=${IMAGE_PROJECT} \
    --boot-disk-size=${DISK_SIZE}GB \
    --boot-disk-type=pd-ssd \
    --tags=http-server,https-server \
    --metadata=startup-script='#!/bin/bash
echo "ClipperApp VM started at $(date)" >> /var/log/clipperapp-boot.log
' \
    --quiet

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe ${VM_NAME} \
    --zone=${ZONE} \
    --project=${PROJECT_ID} \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "   ✅ VM created: ${VM_NAME}"
echo "   📍 External IP: ${EXTERNAL_IP}"

# ─── Upload Code ─────────────────────────────────────────
echo ""
echo "📤 [4/4] Uploading ClipperApp code..."

# Get the directory of this script, then go up to project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Create tarball excluding heavy files
cd ${PROJECT_ROOT}
tar czf /tmp/clipperapp.tar.gz \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='workspace' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='frontend/dist' \
    --exclude='logs' \
    .

# Upload to VM
gcloud compute scp /tmp/clipperapp.tar.gz ${VM_NAME}:/tmp/ \
    --zone=${ZONE} \
    --project=${PROJECT_ID} \
    --quiet

# Extract and setup on VM
gcloud compute ssh ${VM_NAME} \
    --zone=${ZONE} \
    --project=${PROJECT_ID} \
    --quiet \
    --command="
sudo mkdir -p /opt/clipperapp/src
sudo chown \$(whoami):\$(whoami) /opt/clipperapp
cd /opt/clipperapp/src
tar xzf /tmp/clipperapp.tar.gz
rm /tmp/clipperapp.tar.gz
echo '✅ Code extracted to /opt/clipperapp/src'
"

echo "   ✅ Code uploaded"

# ─── Summary ─────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                ✅ GCP Provisioning Complete!               ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║                                                            ║"
echo "║  VM:  ${VM_NAME}                                           "
echo "║  IP:  ${EXTERNAL_IP}                                       "
echo "║  Zone: ${ZONE}                                             "
echo "║                                                            ║"
echo "║  Next steps:                                               ║"
echo "║  1. SSH into the VM:                                       ║"
echo "║     gcloud compute ssh ${VM_NAME} --zone=${ZONE}           "
echo "║                                                            ║"
echo "║  2. Run the setup script:                                  ║"
echo "║     cd /opt/clipperapp/src                                 ║"
echo "║     bash deploy/gcp/setup.sh                               ║"
echo "║                                                            ║"
echo "║  3. Configure .env:                                        ║"
echo "║     nano /opt/clipperapp/src/.env                           ║"
echo "║                                                            ║"
echo "║  4. Start the app:                                         ║"
echo "║     sudo systemctl start clipperapp nginx                  ║"
echo "║                                                            ║"
echo "║  5. Access at: http://${EXTERNAL_IP}                       "
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
