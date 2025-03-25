import os
import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
from datetime import datetime
import uuid
from kubernetes import client, config
import socket
from parser import build_job_manifest

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://appuser:appuser123@mongo:27017/taskdb?authSource=admin")

# 初始化客户端
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.taskdb
tasks_collection = db.tasks

kafka_producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: str(v).encode('utf-8')
)

# Kafka主题
TASK_TOPIC = "tasks"

class KubernetesJobManager:
    def __init__(self):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.batch_api = client.BatchV1Api()

    def submit_job(self, job_manifest):
        try:
            job = self.batch_api.create_namespaced_job(
                namespace="default",
                body=job_manifest
            )
            return job.metadata.name
        except Exception as e:
            logger.error(f"Failed to submit job: {str(e)}")
            raise

# API端点
@app.route('/api/tasks', methods=['POST'])
def create_task():
    """创建任务并发布到Kafka"""
    task_data = request.json
    task_id = str(uuid.uuid4())
    
    # 保存到MongoDB
    task_doc = {
        "_id": task_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
        **task_data
    }
    tasks_collection.insert_one(task_doc)
    
    # 发布到Kafka
    kafka_producer.send(TASK_TOPIC, value=task_id)
    logger.info(f"Published task {task_id} to Kafka")
    
    return jsonify({"task_id": task_id, "status": "pending"}), 202

# 消费者线程
def task_consumer():
    consumer = KafkaConsumer(
        TASK_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id="task-processor",
        auto_offset_reset="earliest"
    )
    
    job_manager = KubernetesJobManager()
    
    for message in consumer:
        task_id = message.value.decode()
        logger.info(f"Processing task: {task_id}")
        
        try:
            # 获取任务详情
            task = tasks_collection.find_one({"_id": task_id})
            if not task:
                logger.warning(f"Task {task_id} not found")
                continue
                
            # 构建Job Manifest (假设有build_job_manifest函数)
            job_manifest = build_job_manifest(task)
            
            # 提交到Kubernetes
            job_name = job_manager.submit_job(job_manifest)
            
            # 更新任务状态
            tasks_collection.update_one(
                {"_id": task_id},
                {"$set": {"status": "processing", "k8s_job": job_name}}
            )
            
            logger.info(f"Successfully processed task {task_id}")
            
        except Exception as e:
            logger.error(f"Failed to process task {task_id}: {str(e)}")
            tasks_collection.update_one(
                {"_id": task_id},
                {"$set": {"status": "failed", "error": str(e)}}
            )

if __name__ == "__main__":
    # 启动Kafka消费者线程
    consumer_thread = Thread(target=task_consumer, daemon=True)
    consumer_thread.start()
    
    # 启动Flask
    app.run(host="0.0.0.0", port=5000)