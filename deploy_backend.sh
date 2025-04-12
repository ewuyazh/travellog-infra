#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Define variables
EC2_IP="3.95.225.43"
PEM_FILE="./TravelAppKey.pem"
BACKEND_DIR="../travellog-backend"
REMOTE_DIR="/home/ec2-user/travellog-backend"

# Check for rsync and ssh
command -v rsync >/dev/null 2>&1 || { echo "rsync is required but not installed. Aborting."; exit 1; }
command -v ssh >/dev/null 2>&1 || { echo "ssh is required but not installed. Aborting."; exit 1; }

echo "Syncing backend files to EC2..."
rsync -avz --exclude 'target/' --exclude '.git/' --exclude 'logs/' --exclude '.idea/' --exclude '.vscode/' \
  -e "ssh -i \"$PEM_FILE\"" "$BACKEND_DIR/" ec2-user@"$EC2_IP":"$REMOTE_DIR"

echo "Connecting to EC2 and deploying..."
ssh -i "$PEM_FILE" ec2-user@"$EC2_IP" << 'EOF'
  set -e
  echo "Switched to EC2. Navigating to backend directory..."
  cd /home/ec2-user/travellog-backend

  echo "Start building Docker image..."
  ./mvnw clean package -DskipTests

  echo "Starting backend using Docker Compose..."
  docker compose --env-file .env --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d
  echo "Backend started successfully."
EOF
