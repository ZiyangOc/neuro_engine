# Neuro Engine Project

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A distributed task processing system with API service and scheduler components.

## Table of Contents
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Development Guide](#development-guide)
- [Deployment Options](#deployment-options)
- [Monitoring Metrics](#monitoring-metrics)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Technology Stack
- Python 3.11
- Flask 3.0
- APScheduler 4.0
- MongoDB 7.0
- Docker 24.0
- Kubernetes 1.28

## Quick Start

### System Requirements
- Linux server (Recommended: Ubuntu 22.04)
- Minimum: 4GB RAM, 2 CPU cores
- Internet connection required

## Development Guide

1. Local environment setup:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

2. Access API documentation:
```bash
# After starting development server
http://localhost:5000/swagger
```

3. Code quality checks:
```bash
flake8 neuro_engine/
mypy neuro_engine/
```

## Deployment Options

### 1. Kubernetes Deployment (Minikube)
```bash
# Start minikube cluster
./deploy.sh k8s

# Access services
minikube service list
```

### 2. Docker Compose Deployment
```bash
# Start all services
./deploy.sh docker

# View logs
docker-compose logs -f
```

### Environment Variables Configuration
```bash
# Copy example config
cp .env.example .env

# Modify these configurations as needed:
# MONGO_ROOT_USER=admin
# MONGO_ROOT_PASSWORD=your-root-password
# MONGO_USER=appuser
# MONGO_PASSWORD=your-app-password
```

## Service Verification
```bash
curl http://localhost:30080/healthcheck
# Expected response: {"status":"healthy"}
```

## Monitoring Metrics
Prometheus metrics endpoint:
```bash
curl http://localhost:30080/metrics
```

## Testing
Run test suite:
```bash
pytest tests/ -v
```

Generate coverage report:
```bash
pytest --cov=neuro_engine --cov-report=html tests/
```

## Contributing
1. Fork the repository
2. Create feature branch (`git checkout -b feature/your-feature`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push branch (`git push origin feature/your-feature`)
5. Create Pull Request

Code standards:
- Follow PEP8 guidelines
- All functions must have type annotations
- Minimum 80% test coverage

## License
[Apache License 2.0](LICENSE)

## System Architecture
![系统架构图](docs/architecture.png)
