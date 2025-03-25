import os
import logging
from flask import Flask, request, jsonify
from pymongo import MongoClient
from kafka import KafkaProducer, KafkaConsumer
from threading import Thread
from datetime import datetime
import uuid
from kubernetes import client, config
import time
import json
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://appuser:appuser123@mongo:27017/taskdb?authSource=admin")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "3600"))  # 1 hour default
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))

# Prometheus metrics
TASKS_CREATED = Counter('tasks_created_total', 'Total tasks created')
TASKS_COMPLETED = Counter('tasks_completed_total', 'Total tasks completed', ['status'])
TASK_PROCESSING_TIME = Histogram('task_processing_seconds', 'Task processing time in seconds')
ACTIVE_TASKS = Gauge('active_tasks', 'Currently active tasks')
TASK_QUEUE_SIZE = Gauge('task_queue_size', 'Number of tasks waiting in queue')

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize clients
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.taskdb
tasks_collection = db.tasks
task_history_collection = db.task_history

# Initialize Kafka producer
kafka_producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Kafka topics
TASK_TOPIC = "tasks"
TASK_EVENTS_TOPIC = "task_events"

class KubernetesJobManager:
    def __init__(self):
        # Initialize Kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self.batch_api = client.BatchV1Api()
    
    def submit_job(self, job_manifest):
        # Submit job to Kubernetes
        try:
            job = self.batch_api.create_namespaced_job(
                namespace="default",
                body=job_manifest
            )
            return job.metadata.name
        except Exception as e:
            logger.error(f"Failed to submit job: {str(e)}")
            raise

# API Endpoints
@app.route('/api/tasks', methods=['POST'])
@limiter.limit("10/minute")
def create_task():
    """Create a new task"""
    try:
        task_data = request.json
        
        # Validate input
        if not task_data.get('command'):
            return jsonify({"error": "Command is required"}), 400
            
        # Generate task ID
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        # Create task document
        task_doc = {
            "_id": task_id,
            "status": "pending",
            "created_at": created_at,
            "created_by": get_remote_address(),
            "priority": task_data.get('priority', 'normal'),
            "attempts": 0,
            "timeout": task_data.get('timeout', TASK_TIMEOUT),
            **task_data
        }
        
        # Save to MongoDB
        tasks_collection.insert_one(task_doc)
        
        # Publish to Kafka
        kafka_producer.send(TASK_TOPIC, value={
            "task_id": task_id,
            "timestamp": str(created_at)
        })
        
        # Update metrics
        TASKS_CREATED.inc()
        TASK_QUEUE_SIZE.inc()
        
        logger.info(f"Created new task {task_id}")
        
        return jsonify({
            "task_id": task_id,
            "status": "pending",
            "created_at": created_at.isoformat()
        }), 202
        
    except Exception as e:
        logger.error(f"Task creation failed: {str(e)}")
        return jsonify({"error": "Task creation failed", "details": str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Get task status"""
    try:
        task = tasks_collection.find_one({"_id": task_id})
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
        logger.error(f"Failed to get task status: {str(e)}")
        return jsonify({"error": "Failed to get task status"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Service health check"""
    try:
        # Check MongoDB connection
        mongo_client.admin.command('ping')
        # Check Kafka connection
        kafka_producer.list_topics()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def task_consumer():
    """Consume tasks from Kafka and process them"""
    consumer = KafkaConsumer(
        TASK_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id="task-processor",
        auto_offset_reset="earliest"
    )
    
    job_manager = KubernetesJobManager()
    
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
            task = tasks_collection.find_one({"_id": task_id})
            if not task:
                logger.warning(f"Task {task_id} not found")
                continue
                
            # Check if task is expired
            if is_task_expired(task):
                mark_task_as_failed(task_id, "Task timeout")
                continue
                
            # Build job manifest
            job_manifest = build_job_manifest(task)
            
            # Submit to Kubernetes
            job_name = job_manager.submit_job(job_manifest)
            
            # Update task status
            update_data = {
                "status": "processing",
                "k8s_job": job_name,
                "started_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "$inc": {"attempts": 1}
            }
            tasks_collection.update_one({"_id": task_id}, {"$set": update_data})
            
            # Record processing time
            processing_time = time.time() - start_time
            TASK_PROCESSING_TIME.observe(processing_time)
            
            logger.info(f"Successfully submitted task {task_id} to Kubernetes")
            
        except Exception as e:
            logger.error(f"Failed to process task {task_id}: {str(e)}")
            if task_id:
                handle_failed_task(task_id, str(e))
        finally:
            ACTIVE_TASKS.dec()

def is_task_expired(task):
    """Check if task has expired"""
    timeout = task.get("timeout", TASK_TIMEOUT)
    created_at = task["created_at"]
    return (datetime.utcnow() - created_at).total_seconds() > timeout

def handle_failed_task(task_id, error):
    """Handle failed task with retry logic"""
    task = tasks_collection.find_one({"_id": task_id})
    if not task:
        return
        
    current_attempts = task.get("attempts", 0)
    
    if current_attempts < MAX_RETRIES:
        # Retry task with exponential backoff
        retry_delay = min(2 ** current_attempts, 60)  # Max 60 seconds
        time.sleep(retry_delay)
        
        # Republish to Kafka
        kafka_producer.send(TASK_TOPIC, value={
            "task_id": task_id,
            "timestamp": str(datetime.utcnow())
        })
        
        logger.info(f"Retrying task {task_id}, attempt {current_attempts + 1}")
    else:
        # Mark as failed after max retries
        mark_task_as_failed(task_id, error)

def mark_task_as_failed(task_id, error):
    """Mark task as failed"""
    tasks_collection.update_one(
        {"_id": task_id},
        {"$set": {
            "status": "failed",
            "error": error,
            "completed_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    TASKS_COMPLETED.labels(status="failed").inc()
    logger.error(f"Task {task_id} failed: {error}")

def result_consumer():
    """Consume task results from Kubernetes"""
    consumer = KafkaConsumer(
        TASK_EVENTS_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id="result-processor"
    )
    
    for message in consumer:
        try:
            event = json.loads(message.value.decode())
            task_id = event["task_id"]
            status = event["status"]
            
            # Update task status
            update_data = {
                "status": status,
                "completed_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if status == "completed":
                update_data["result"] = event.get("result")
            else:
                update_data["error"] = event.get("error")
                
            tasks_collection.update_one(
                {"_id": task_id},
                {"$set": update_data}
            )
            
            # Archive to history
            task = tasks_collection.find_one({"_id": task_id})
            if task:
                task_history_collection.insert_one(task)
                tasks_collection.delete_one({"_id": task_id})
            
            # Update metrics
            TASKS_COMPLETED.labels(status=status).inc()
            
            logger.info(f"Task {task_id} completed with status: {status}")
            
        except Exception as e:
            logger.error(f"Failed to process task result: {str(e)}")

# Start Prometheus metrics server
start_http_server(PROMETHEUS_PORT)

if __name__ == "__main__":
    # Start Kafka consumer thread
    consumer_thread = Thread(target=task_consumer, daemon=True)
    consumer_thread.start()
    
    # Start result consumer thread
    result_thread = Thread(target=result_consumer, daemon=True)
    result_thread.start()
    
    # Start Flask application
    app.run(host="0.0.0.0", port=5000)