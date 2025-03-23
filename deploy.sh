#!/bin/bash
set -e

# Install system dependencies
echo "Installing system packages..."
sudo apt-get update && sudo apt-get install -y docker.io curl git

# Install k3s (lightweight Kubernetes)
echo "Installing Kubernetes..."
curl -sfL https://get.k3s.io | sh -
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Build Docker images
echo "Building Docker images..."
docker build -t neuro-engine-api:1.0 -f api/Dockerfile .
docker build -t neuro-engine-scheduler:1.0 -f scheduler/Dockerfile.scheduler .

# Deploy to Kubernetes
echo "Deploying MongoDB..."
kubectl apply -f k8s/mongodb.yaml

echo "Waiting for MongoDB to be ready..."
kubectl wait --for=condition=ready pod -l app=mongodb --timeout=120s

echo "Deploying API service..."
kubectl apply -f k8s/api-service.yaml

echo "Deploying scheduler..."
kubectl apply -f k8s/scheduler.yaml

# Verify deployment
echo "Checking services status..."
kubectl get pods -o wide
echo -e "\nDeployment completed! API endpoint: http://$(curl -s ifconfig.me):30080"
