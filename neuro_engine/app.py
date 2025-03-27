import os
import logging
import json
import uuid
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from flask import Flask, request, jsonify
from flask_cors import CORS

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from kafka import KafkaProducer, KafkaConsumer
from kubernetes import client, config
from threading import Thread
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from parser import TaskValidator,TaskDocumentBuilder,KubernetesJobBuilder

# Enhanced Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('task_manager.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Application Configuration
class AppConfig:
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://appuser:appuser123@mongo:27017/taskdb?authSource=admin")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "3600"))  # 1 hour default
    PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))
    NAMESPACE = os.getenv("K8S_NAMESPACE", "default")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Prometheus Metrics
TASKS_CREATED = Counter('tasks_created_total', 'Total tasks created')
TASKS_COMPLETED = Counter('tasks_completed_total', 'Total tasks completed', ['status'])
TASK_PROCESSING_TIME = Histogram('task_processing_seconds', 'Task processing time in seconds')
ACTIVE_TASKS = Gauge('active_tasks', 'Currently active tasks')
TASK_QUEUE_SIZE = Gauge('task_queue_size', 'Number of tasks waiting in queue')

class MongoDBManager:
    def __init__(self, uri: str):
        try:
            self.client = MongoClient(uri)
            self.db = self.client.taskdb
            self.tasks_collection = self.db.tasks
            self.task_history_collection = self.db.task_history
        except PyMongoError as e:
            logger.error(f"MongoDB connection error: {e}")
            raise

    def insert_task(self, task_doc: Dict[str, Any]) -> str:
        try:
            result = self.tasks_collection.insert_one(task_doc)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to insert task: {e}")
            raise

    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        try:
            result = self.tasks_collection.update_one(
                {"_id": task_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self.tasks_collection.find_one({"_id": task_id})
        except PyMongoError as e:
            logger.error(f"Failed to retrieve task {task_id}: {e}")
            return None

    def archive_task(self, task_id: str) -> bool:
        try:
            task = self.tasks_collection.find_one({"_id": task_id})
            if task:
                self.task_history_collection.insert_one(task)
                self.tasks_collection.delete_one({"_id": task_id})
                return True
            return False
        except PyMongoError as e:
            logger.error(f"Failed to archive task {task_id}: {e}")
            return False

class KubernetesJobManager:
    def __init__(self, namespace: str = "default"):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.batch_api = client.BatchV1Api()
        self.namespace = namespace

    def submit_job(self, job_manifest: Dict[str, Any]) -> str:
        try:
            job = self.batch_api.create_namespaced_job(
                namespace=self.namespace,
                body=job_manifest
            )
            return job.metadata.name
        except Exception as e:
            logger.error(f"Failed to submit job: {str(e)}")
            raise

class TaskManager:
    def __init__(self, config: AppConfig, mongodb_manager: MongoDBManager, job_manager: KubernetesJobManager):
        self.config = config
        self.mongodb_manager = mongodb_manager
        self.job_manager = job_manager
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        # 输入验证
        TaskValidator.validate(task_data)

        # 构建标准文档
        task_id = str(uuid.uuid4())
        task_doc = TaskDocumentBuilder.build(
            task_id=task_id,
            task_data=task_data,
            default_timeout=self.config.TASK_TIMEOUT,
            default_max_retries=self.config.MAX_RETRIES
        )

        # 保存到数据库（保持不变）
        self.mongodb_manager.insert_task(task_doc)
        
        # 发送Kafka消息（保持不变）
        self.kafka_producer.send("tasks", value={
            "task_id": task_id,
            "timestamp": str(task_doc['created_at'])
        })

        # 更新指标（保持不变）
        TASKS_CREATED.inc()
        TASK_QUEUE_SIZE.inc()

        return {
            "task_id": task_id,
            "status": "pending",
            "created_at": str(task_doc['created_at'])
        }

    def handle_task_result(self, event: Dict[str, Any]) -> None:
        task_id = event["task_id"]
        status = event["status"]

        update_data = {
            "status": status,
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        if status == "completed":
            update_data["result"] = event.get("result")
        else:
            update_data["error"] = event.get("error")

        self.mongodb_manager.update_task(task_id, update_data)
        self.mongodb_manager.archive_task(task_id)

        # Update metrics
        TASKS_COMPLETED.labels(status=status).inc()
        logger.info(f"Task {task_id} completed with status: {status}")

def task_consumer(task_manager: TaskManager, mongodb_manager: MongoDBManager):
    """Consume tasks from Kafka and process them"""
    consumer = KafkaConsumer(
        "tasks",
        bootstrap_servers=task_manager.config.KAFKA_BROKER,
        group_id="task-processor",
        auto_offset_reset="earliest"
    )

    job_manager = KubernetesJobManager(task_manager.config.NAMESPACE)

    for message in consumer:
        try:
            data = json.loads(message.value.decode())
            task_id = data["task_id"]

            # Update metrics
            TASK_QUEUE_SIZE.dec()
            ACTIVE_TASKS.inc()

            start_time = time.time()
            logger.info(f"Processing task {task_id}")

            # Get task details
            task = mongodb_manager.get_task(task_id)
            if not task:
                logger.warning(f"Task {task_id} not found")
                continue

            # Check task timeout
            created_at = task["created_at"]
            timeout = task.get("timeout", task_manager.config.TASK_TIMEOUT)
            if (datetime.utcnow() - created_at).total_seconds() > timeout:
                mongodb_manager.update_task(task_id, {
                    "status": "failed",
                    "error": "Task timeout"
                })
                continue

            # Submit to Kubernetes
            job_manifest = KubernetesJobBuilder.build_manifest(
                task_id=task_id,
                task_execution=task["execution"],
                namespace=task_manager.config.NAMESPACE
            )

            job_name = job_manager.submit_job(job_manifest)

            # Update task status
            update_data = {
                "status": "processing",
                "k8s_job": job_name,
                "updated_at": datetime.utcnow(),
                "$inc": {"attempts": 1}
            }
            mongodb_manager.update_task(task_id, update_data)

            # Record processing time
            processing_time = time.time() - start_time
            TASK_PROCESSING_TIME.observe(processing_time)

            logger.info(f"Successfully submitted task {task_id} to Kubernetes")

        except Exception as e:
            logger.error(f"Failed to process task {task_id}: {str(e)}")
        finally:
            ACTIVE_TASKS.dec()

def result_consumer(task_manager: TaskManager):
    """Consume task results from Kubernetes"""
    consumer = KafkaConsumer(
        "task_events",
        bootstrap_servers=task_manager.config.KAFKA_BROKER,
        group_id="result-processor"
    )

    for message in consumer:
        try:
            event = json.loads(message.value.decode())
            task_manager.handle_task_result(event)
        except Exception as e:
            logger.error(f"Failed to process task result: {str(e)}")

def create_app(config: AppConfig, mongodb_manager: MongoDBManager, job_manager: KubernetesJobManager):
    app = Flask(__name__)
    CORS(app)
    
    task_manager = TaskManager(config, mongodb_manager, job_manager)

    @app.route('/api/tasks', methods=['POST'])
    def create_task():
        try:
            raw_data = request.json
            result = task_manager.create_task(raw_data)
            return jsonify(result), 202
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.error(f"Task creation error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @app.route('/api/tasks/<task_id>', methods=['GET'])
    def get_task_status(task_id):
        try:
            task = mongodb_manager.get_task(task_id)
            if not task:
                return jsonify({"error": "Task not found"}), 404
            
            return jsonify({
                "task_id": task_id,
                "status": task.get("status"),
                "created_at": task.get("created_at").isoformat(),
                "updated_at": task.get("updated_at", task.get("created_at")).isoformat(),
                "k8s_job": task.get("k8s_job"),
                "error": task.get("error")
            }), 200
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return jsonify({"error": "Internal server error"}), 500

    @app.route('/health', methods=['GET'])
    def health_check():
        try:
            # Basic health checks
            mongodb_manager.client.admin.command('ping')
            return jsonify({"status": "healthy"}), 200
        except Exception as e:
            return jsonify({"status": "unhealthy", "error": str(e)}), 500

    return app

if __name__ == "__main__":
    appconfig = AppConfig()
    mongodb_manager = MongoDBManager(appconfig.MONGO_URI)
    job_manager = KubernetesJobManager(appconfig.NAMESPACE)
    app = create_app(appconfig, mongodb_manager, job_manager)
    app.run(host="0.0.0.0", port=5000, debug=appconfig.DEBUG)
else:
    # 提供给 Gunicorn 使用
    appconfig = AppConfig()
    mongodb_manager = MongoDBManager(appconfig.MONGO_URI)
    job_manager = KubernetesJobManager(appconfig.NAMESPACE)
    app = create_app(appconfig, mongodb_manager, job_manager)