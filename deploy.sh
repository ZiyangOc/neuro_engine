#!/bin/bash
set -e

DEPLOY_MODE=${1:-k8s}

case $DEPLOY_MODE in
  docker)
    echo "Starting Docker deployment..."
    docker-compose up --build -d
    exit 0
    ;;
  k8s)
    echo "Starting Kubernetes deployment..."
    ;;
  *)
    echo "Usage: $0 [docker|k8s]"
    exit 1
    ;;
esac

# Check and install system dependencies
echo "Checking system dependencies..."
declare -a deps=("docker" "curl" "git")
missing_deps=()

for dep in "${deps[@]}"; do
  if ! command -v $dep &> /dev/null; then
    missing_deps+=("$dep")
  fi
done

if [ ${#missing_deps[@]} -gt 0 ]; then
  echo "Installing missing packages: ${missing_deps[*]}..."
  sudo apt-get update && sudo apt-get install -y "${missing_deps[@]}"
fi

# Check and install minikube
if [ ! -f /usr/local/bin/minikube ]; then
  echo "Installing minikube..."
  curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
  sudo install minikube-linux-amd64 /usr/local/bin/minikube
else
  echo "minikube already installed at /usr/local/bin/minikube"
fi

# Start minikube if not running
if ! minikube status | grep -q 'Running'; then
  echo "Starting minikube cluster..."
  minikube start --driver=docker
else
  echo "minikube cluster is already running"
fi

export KUBECONFIG=~/.kube/config

# Generate secrets
echo "Generating Kubernetes secrets..."
MONGO_PASS=$(openssl rand -base64 16)
kubectl create secret generic mongodb-secret \
  --from-literal=username=admin \
  --from-literal=password=$MONGO_PASS \
  --from-literal=connection-string="mongodb://admin:$MONGO_PASS@mongodb:27017/?authSource=admin"

# Create storage class using standard provisioner
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ssd-sc
provisioner: k8s.io/minikube-hostpath
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
EOF

# Build Docker images and load into minikube
echo "Building Docker images..."
docker build -t neuro-engine-api:1.0 -f api/Dockerfile .
docker build -t neuro-engine-scheduler:1.0 -f scheduler/Dockerfile.scheduler .
minikube image load neuro-engine-api:1.0
minikube image load neuro-engine-scheduler:1.0

# Deploy to Kubernetes
echo "Deploying MongoDB..."
kubectl apply -f k8s/mongodb.yaml

echo "Waiting for MongoDB to be ready..."
kubectl wait --for=condition=ready pod -l app=mongodb --timeout=300s

echo "Initializing MongoDB replica set..."
kubectl exec deploy/mongodb -- mongo --eval 'rs.initiate({_id: "rs0", members: [{_id: 0, host: "mongodb-0.mongodb:27017"}, {_id: 1, host: "mongodb-1.mongodb:27017"}, {_id: 2, host: "mongodb-2.mongodb:27017"}]})'

echo "Deploying API service..."
kubectl apply -f k8s/api-service.yaml

echo "Deploying scheduler..."
kubectl apply -f k8s/scheduler.yaml

# Verify deployment
echo "Checking services status..."
kubectl get pods -o wide -w

echo -e "\nDeployment completed! Access endpoints:"
echo "API: $(minikube service api-service --url)"
echo "MongoDB admin: mongodb://admin:$MONGO_PASS@$(minikube ip):30017"
