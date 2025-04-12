#!/bin/bash
set -eo pipefail  # Strict error handling

# ===== Configuration =====
DEPLOY_ENV="production"
APP_VERSION="1.0.0"
DOCKER_IMAGE_NAME="travel-react-app"
REACT_APP_NAME="react-app"
SPRINGBOOT_SERVICE="app"  # Spring Boot container name
AWS_EC2_HOST="3.95.225.43"
AWS_EC2_USER="ec2-user"   # Add this if it's missing
SSH_KEY="$(cd "$(dirname "$0")" && pwd)/TravelAppKey.pem"
DOCKER_NETWORK="travel-global-network"
NGINX_CONF="nginx.production.conf"
COMPOSE_FILE="docker-compose.yml"
BUILD_CACHE_DIR="./.build-cache"
GIT_HASH=$(git rev-parse --short HEAD)
FRONTEND_DIR="../travellog-frontend"  # Adjust path to frontend
INFRA_DIR="."  # Current directory is the infra folder
DEPLOY_DIR="/home/ec2-user/"

# ===== Validate Environment =====
cd ${FRONTEND_DIR}

if [ ! -f ".env.$DEPLOY_ENV" ]; then
  echo "ERROR: .env.$DEPLOY_ENV not found!"
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "ERROR: $COMPOSE_FILE missing"
  exit 1
fi

# ===== Build with Cache =====
echo "=== Building Production Image with Cache ==="
mkdir -p "$BUILD_CACHE_DIR"
docker buildx build \
  -t "$DOCKER_IMAGE_NAME:$APP_VERSION" \
  -t "$DOCKER_IMAGE_NAME:$APP_VERSION-$GIT_HASH" \
  .

# ===== Prepare Deployment Package =====
DEPLOY_PACKAGE="deploy-$(date +%s).tar.gz"
tar czf "$DEPLOY_PACKAGE" \
  "$COMPOSE_FILE" \
  .env.$DEPLOY_ENV \
  Dockerfile

# ===== Secure Transfer to EC2 =====
cd "$INFRA_DIR"  # Switch back to the infra directory
echo "=== Transferring to EC2 ==="
scp -i "$SSH_KEY" -o StrictHostKeyChecking=no \
  "$DEPLOY_PACKAGE" \
  "$AWS_EC2_USER@$AWS_EC2_HOST:/tmp/"

# ===== Remote Execution on EC2 =====
ssh -i "$SSH_KEY" -T "$AWS_EC2_USER@$AWS_EC2_HOST" << 'EOSSH'
set -eo pipefail

TIMESTAMP=$(date +%Y%m%d%H%M%S)
CURRENT_DIR="$DEPLOY_DIR/$TIMESTAMP"
DEPLOY_ENV="production"
COMPOSE_FILE="docker-compose.production.yml"

echo "=== Setting Up Deployment ==="
mkdir -p "$CURRENT_DIR"
tar xzf /tmp/deploy-*.tar.gz -C "$CURRENT_DIR"
rm -f /tmp/deploy-*.tar.gz

echo "=== Loading Environment ==="
export \$(grep -v '^#' "$CURRENT_DIR/.env.$DEPLOY_ENV" | xargs)

echo "=== Network Setup ==="
docker network inspect travel-global-network >/dev/null 2>&1 || \
  docker network create --driver bridge travel-global-network

echo "=== Deploying with Docker Compose ==="
docker-compose -f "$CURRENT_DIR/$COMPOSE_FILE" pull --quiet
docker-compose -f "$CURRENT_DIR/$COMPOSE_FILE" up -d --no-deps --build react-app

echo "=== Health Verification ==="
for i in {1..10}; do
  CONTAINER_ID=\$(docker ps -q -f name=react-app)
  HEALTH=\$(docker inspect --format='{{.State.Health.Status}}' "\$CONTAINER_ID" 2>/dev/null || echo "starting")
  [ "\$HEALTH" = "healthy" ] && break
  sleep 5
done

if [ "\$HEALTH" != "healthy" ]; then
  echo "ERROR: Deployment failed health check"
  docker logs "\$CONTAINER_ID"
  exit 1
fi

echo "=== Cleaning Old Deployments ==="
find "$DEPLOY_DIR" -mindepth 1 -maxdepth 1 -type d -not -name "$TIMESTAMP" \
  -exec rm -rf {} +

echo "=== Current Services ==="
docker-compose -f "$CURRENT_DIR/$COMPOSE_FILE" ps
EOSSH

# ===== Local Cleanup =====
rm "$DEPLOY_PACKAGE"
echo "=== Production Deployment Complete ==="