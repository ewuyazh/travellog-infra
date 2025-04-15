#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Usage function
usage() {
  echo "Usage: $0 <EC2_PUBLIC_IP> <RDS_ENDPOINT>"
  exit 1
}

# Check for EC2 IP and RDS endpoint
if [ -z "$1" ] || [ -z "$2" ]; then
  usage
fi

# Variables
EC2_IP="$1"
RDS_ENDPOINT="$2"

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

ENV_FILE="$BACKEND_DIR/.env.prod"

# Replace the placeholder RDS_ENDPOINT with the actual value
sed -i '' "s|jdbc:mysql://RDS_ENDPOINT:3306|jdbc:mysql://$RDS_ENDPOINT:3306|" "$ENV_FILE"

echo "DATABASE_URL updated in $ENV_FILE"

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
  #rm -rf travellog-backend
  #echo "Source code directory removed from EC2 instance."
EOF

echo "Deployment to EC2 instance at $EC2_IP completed successfully."
