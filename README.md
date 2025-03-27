# Neuro Engine Project

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A distributed task processing system with API service and scheduler components.

## 目录
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [开发指南](#开发指南)
- [部署选项](#部署选项)
- [监控指标](#监控指标)
- [测试](#测试)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## 技术栈
- Python 3.11
- Flask 3.0
- APScheduler 4.0
- MongoDB 7.0
- Docker 24.0
- Kubernetes 1.28

## 快速开始

### 环境要求
- Linux 服务器（推荐 Ubuntu 22.04）
- 最低配置：4GB 内存，2 CPU 核心
- 需要互联网连接

## 开发指南

1. 本地开发环境配置：
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

2. API 文档访问：
```bash
# 启动开发服务器后访问
http://localhost:5000/swagger
```

3. 代码质量检查：
```bash
flake8 neuro_engine/
mypy neuro_engine/
```

## 部署选项

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

## 服务验证
```bash
curl http://localhost:30080/healthcheck
# 预期返回 {"status":"healthy"}
```

## 监控指标
Prometheus metrics 端点：
```bash
curl http://localhost:30080/metrics
```

## 测试指南
运行测试套件：
```bash
pytest tests/ -v
```

生成覆盖率报告：
```bash
pytest --cov=neuro_engine --cov-report=html tests/
```

## 贡献指南
1. Fork 项目仓库
2. 创建特性分支 (`git checkout -b feature/your-feature`)
3. 提交修改 (`git commit -am '添加新功能'`)
4. 推送分支 (`git push origin feature/your-feature`)
5. 创建 Pull Request

代码规范要求：
- 遵循 PEP8 规范
- 所有函数必须有类型注解
- 测试覆盖率不低于 80%

## 许可证
[Apache License 2.0](LICENSE)

## 系统架构
![系统架构图](docs/architecture.png)
