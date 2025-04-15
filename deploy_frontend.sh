#!/bin/bash
set -eo pipefail

# === Input Arguments ===
if [ -z "$1" ]; then
  echo "Usage: ./deploy_frontend.sh <EC2_PUBLIC_IP>"
  exit 1
fi

AWS_EC2_HOST="$1"
AWS_EC2_USER="ec2-user"
SSH_KEY="./TravelAppKey.pem"
DEPLOY_ENV="production"

# === Paths ===
FRONTEND_DIR="../travellog-frontend"
DEPLOY_PACKAGE="/tmp/deploy-$(date +%s).tar.gz"

echo "=== Starting Deployment Script ==="
echo "==> Using EC2 Host: $AWS_EC2_HOST"

# === Validate Frontend Directory ===
echo "=== Navigating to frontend directory: $FRONTEND_DIR ==="
cd "$FRONTEND_DIR"

# === Validate Files ===
echo "=== Validating required files ==="
[ -f "vite.config.ts" ] || { echo "Missing vite.config.ts"; exit 1; }
[ -f "package.json" ] || { echo "Missing package.json"; exit 1; }

# === Create Deployment Package ===
echo "=== Preparing deployment package ==="
echo "==> Creating tarball: $DEPLOY_PACKAGE"
tar -czf "$DEPLOY_PACKAGE" . --exclude='node_modules' --exclude='build'

# === Clean up Old Tarballs on EC2 ===
echo "=== Cleaning up old tarballs on EC2 ==="
ssh -i "$SSH_KEY" "$AWS_EC2_USER@$AWS_EC2_HOST" "rm -f /tmp/deploy-*.tar.gz"

# === Return to Infra Directory ===
cd - > /dev/null

# === Transfer Deployment Package ===
echo "=== Transferring deployment package to EC2 ==="
scp -i "$SSH_KEY" "$DEPLOY_PACKAGE" "$AWS_EC2_USER@$AWS_EC2_HOST:/tmp/"

# === Execute Deployment on EC2 ===
echo "=== Executing deployment on EC2 ==="
ssh -i "$SSH_KEY" -T "$AWS_EC2_USER@$AWS_EC2_HOST" <<EOSSH
DEPLOY_PACKAGE="$DEPLOY_PACKAGE"
DEPLOY_ENV="$DEPLOY_ENV"
bash -s <<'INNERSCRIPT'
set -eo pipefail

LOG_DIR="/home/ec2-user/deploy-logs"
LOGFILE="$LOG_DIR/deploy-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOGFILE") 2>&1

echo "=== Starting frontend deployment on EC2 ==="
echo "DEPLOY_PACKAGE: \$DEPLOY_PACKAGE"
echo "DEPLOY_ENV: \$DEPLOY_ENV"

# === Unpack Package ===
echo "=== Unpacking deployment package ==="
mkdir -p /tmp/frontend-deploy
rm -rf /tmp/frontend-deploy/*
tar -xzf "\$DEPLOY_PACKAGE" -C /tmp/frontend-deploy

cd /tmp/frontend-deploy || { echo "Unpack failed"; exit 1; }

# === Install & Build ===
echo "=== Installing frontend dependencies ==="
npm ci

echo "=== Building frontend ==="
npm run build

# === Deploy to Web Directory ===
echo "=== Deploying to /var/www/html ==="
sudo rm -rf /var/www/html/*
sudo cp -r dist/* /var/www/html/

echo "✅ Deployment to EC2 complete"
echo "📝 Logs saved to \$LOGFILE"
INNERSCRIPT
EOSSH

# === Clean Up Local Tarball ===
echo "=== Cleaning up local deployment package ==="
rm -f "$DEPLOY_PACKAGE"

echo "=== Deployment Complete! 🎉 ==="