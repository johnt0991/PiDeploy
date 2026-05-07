#!/bin/bash

set -e

echo "🔄 Updating system..."
sudo apt update && sudo apt upgrade -y

echo "📦 Installing dependencies..."
sudo apt install -y curl git

echo "🐳 Checking Docker..."

if command -v docker >/dev/null 2>&1; then
  echo "✅ Docker already installed"
else
  echo "⬇️ Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

echo "📦 Checking Docker Compose..."
if docker compose version >/dev/null 2>&1; then
  echo "✅ Docker Compose available"
else
  sudo apt install -y docker-compose-plugin
fi

echo "🔧 Ensuring Docker service..."
sudo systemctl enable docker
sudo systemctl start docker

echo "👤 Adding user to docker group..."
sudo usermod -aG docker $USER

echo "📁 Creating directories..."
sudo mkdir -p /srv/docker/{compose,data}
sudo chown -R $USER:$USER /srv/docker

echo "📁 Creating stack directory..."
mkdir -p /srv/docker/compose/core

echo "📝 Writing docker-compose..."
cat <<EOF > /srv/docker/compose/core/docker-compose.yml
version: "3.9"

services:

  uptime-kuma:
    image: louislam/uptime-kuma:latest
    container_name: uptime-kuma
    restart: unless-stopped
    ports:
      - "3001:3001"
    volumes:
      - /srv/docker/data/kuma:/app/data

  glance:
    image: glanceapp/glance:latest
    container_name: glance
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /srv/docker/data/glance/config:/app/config
      - /srv/docker/data/glance/assets:/app/assets
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      TZ: America/Los_Angeles

  steam-achievements-api:
    image: python:3.12-alpine
    container_name: steam-achievements-api
    restart: unless-stopped
    command: python /app/steam_achievements_api.py
    volumes:
      - /srv/docker/data/glance/assets:/app:ro
    environment:
      TZ: America/Los_Angeles
      STEAM_API_KEY: 68AF8D904102838D98D6715733F0B02F
      STEAM_ID: "76561198046289926"
EOF

echo "🚀 Starting containers..."
cd /srv/docker/compose/core
docker compose up -d

# 🔍 Get IP address
IP=$(hostname -I | awk '{print $1}')

echo ""
echo "======================================="
echo "✅ STACK DEPLOYED SUCCESSFULLY"
echo "======================================="
echo ""
echo "🌐 Access your services:"
echo ""
echo "Homepage:      http://$IP:3000"
echo "Uptime Kuma:   http://$IP:3001"
echo ""
echo "======================================="
echo ""
echo "⚠️ IMPORTANT:"
echo "- Run: newgrp docker   OR log out/in"
echo "- Then refresh containers if needed"
echo ""
