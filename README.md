# Neuro Engine Project

A distributed task processing system with API service and scheduler components.

## Features
- REST API for task management
- Background scheduler for task processing
- MongoDB for data storage
- Kubernetes-based deployment
- Docker containerization

## Technology Stack
- Python 3.9+
- Flask REST API
- APScheduler
- MongoDB 5.0
- Docker 20.10+
- Kubernetes (k3s)

## Prerequisites
- Linux server (Ubuntu 22.04 recommended)
- Minimum 4GB RAM, 2 CPU cores
- Internet connection

## Deployment

### Quick Start
```bash
curl -O https://raw.githubusercontent.com/your-repo/neuro-engine/main/deploy.sh
chmod +x deploy.sh
sudo ./deploy.sh
```

### Manual Deployment
1. Install dependencies:
```bash
sudo apt-get update && sudo apt-get install -y docker.io curl
```

2. Install Kubernetes (k3s):
```bash
curl -sfL https://get.k3s.io | sh -
sudo kubectl config use-context default
```

3. Clone repository:
```bash
git clone https://github.com/your-repo/neuro-engine.git
cd neuro-engine
```

4. Build Docker images:
```bash
docker build -t neuro-engine-api:1.0 -f api/Dockerfile .
docker build -t neuro-engine-scheduler:1.0 -f scheduler/Dockerfile.scheduler .
```

5. Deploy to Kubernetes:
```bash
kubectl apply -f k8s/mongodb.yaml
kubectl apply -f k8s/api-service.yaml  
kubectl apply -f k8s/scheduler.yaml
```

## Verification
```bash
curl http://localhost:30080/healthcheck
# Should return {"status":"healthy"}
```

## Architecture
![System Architecture](docs/architecture.png)
