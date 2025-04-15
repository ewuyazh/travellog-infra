#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Usage function
usage() {
  echo "Usage: $0 <EC2_PUBLIC_IP>"
  exit 1
}

# Check if EC2 IP is provided
if [ -z "$1" ]; then
  usage
fi

# Define variables
EC2_IP="$1"
PEM_FILE="./TravelAppKey.pem"
BACKEND_DIR="../travellog-backend"
REMOTE_DIR="/home/ec2-user/travellog-backend"

# Check for required commands
for cmd in rsync ssh; do
  if ! command -v $cmd >/dev/null 2>&1; then
    echo "Error: $cmd is required but not installed. Aborting."
    exit 1
  fi
done

echo "Syncing backend files to EC2 instance at $EC2_IP..."
rsync -avz --exclude-from="$BACKEND_DIR/.rsync-exclude" -e "ssh -i \"$PEM_FILE\"" "$BACKEND_DIR/" ec2-user@"$EC2_IP":"$REMOTE_DIR"

echo "Connecting to EC2 and deploying..."
ssh -i "$PEM_FILE" ec2-user@"$EC2_IP" << 'EOF'
  set -e
  echo "Switched to EC2. Navigating to backend directory..."
  cd /home/ec2-user/travellog-backend

  echo "Starting backend build using Docker Compose..."
  docker compose --env-file .env --env-file .env.prod -f docker-compose.prod.yml build

  echo "Running Docker image..."
  docker compose --env-file .env --env-file .env.prod -f docker-compose.prod.yml up -d

  cd ..
  rm -rf travellog-backend
  echo "Source code directory removed from EC2 instance."
EOF

echo "Deployment to EC2 instance at $EC2_IP completed successfully."