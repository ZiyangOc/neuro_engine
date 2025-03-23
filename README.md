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

## Deployment Options

### 1. Kubernetes Deployment (Minikube)
```bash
# 启动minikube集群
./deploy.sh k8s

# 访问服务
minikube service list
```

### 2. Docker Compose Deployment
```bash
# 启动所有服务
./deploy.sh docker

# 查看日志
docker-compose logs -f
```

### 公共环境变量配置
```bash
# 复制示例配置文件
cp .env.example .env

# 根据需要修改以下配置：
# MONGO_ROOT_USER=admin
# MONGO_ROOT_PASSWORD=your-root-password
# MONGO_USER=appuser
# MONGO_PASSWORD=your-app-password
```

## Verification
```bash
curl http://localhost:30080/healthcheck
# Should return {"status":"healthy"}
```

## Architecture
![System Architecture](docs/architecture.png)
