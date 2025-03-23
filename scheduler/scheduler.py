import os
import time
import logging
from datetime import datetime
from pymongo import MongoClient, errors
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        from dotenv import load_dotenv
        load_dotenv()
        deploy_mode = os.getenv('DEPLOY_MODE', 'k8s')
        if deploy_mode == 'docker':
            self.mongo_uri = os.getenv('MONGO_URI')
        else:
            # Kubernetes模式从Secret获取凭据
            mongo_user = os.getenv('MONGO_USERNAME')
            mongo_pass = os.getenv('MONGO_PASSWORD') 
            self.mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@mongodb:27017/admin?authSource=admin&replicaSet=rs0"
        self.db = self.connect_mongo()
        self.batch_api = client.BatchV1Api()
        self.core_api = client.CoreV1Api()
        
    def connect_mongo(self, max_retries=5, retry_delay=3):
        """Connect to MongoDB with retry mechanism"""
        for attempt in range(max_retries):
            try:
                client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
                client.admin.command('ping')
                return client['taskdb']['tasks']
            except errors.PyMongoError as e:
                logger.error(f"MongoDB connection failed (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        raise RuntimeError("Failed to connect to MongoDB")

    def validate_task_spec(self, task):
        """Validate task specification"""
        required_fields = {
            'execution': ['containerImage'],
            'resources': ['requests'],
            'volumes': list,
            'parameters': dict
        }
        
        for section, fields in required_fields.items():
            if section not in task:
                raise ValueError(f"Missing required section: {section}")
            if isinstance(fields, list):
                for field in fields:
                    if field not in task[section]:
                        raise ValueError(f"{section} missing required field: {field}")

    def create_container_spec(self, task):
        """Create container specification"""
        execution = task['execution']
        return client.V1Container(
            name=f"task-{task['_id'][:8]}",
            image=execution['containerImage'],
            command=execution.get('command', []),
            args=execution.get('args', []),
            env=[client.V1EnvVar(name=k, value=v) for k,v in execution.get('env', {}).items()],
            volume_mounts=[
                client.V1VolumeMount(name=vm['name'], mount_path=vm['mountPath'])
                for vm in task['volumes']
            ],
            resources=client.V1ResourceRequirements(
                requests=task['resources']['requests'],
                limits=task['resources'].get('limits', {})
            )
        )

    def create_volume_spec(self, volume_config):
        """Create volume specification"""
        if volume_config['type'] == 'pvc':
            return client.V1Volume(
                name=volume_config['name'],
                persistentVolumeClaim=client.V1PersistentVolumeClaimVolumeSource(
                    claimName=volume_config['claimName'])
            )
        elif volume_config['type'] == 'secret':
            return client.V1Volume(
                name=volume_config['name'],
                secret=client.V1SecretVolumeSource(secret_name=volume_config['secretName'])
            )
        raise ValueError(f"Unsupported volume type: {volume_config['type']}")

    def create_job_manifest(self, task):
        """Create Kubernetes Job manifest"""
        self.validate_task_spec(task)
        
        job_name = f"task-{task['_id'].replace('-', '')[:16]}"
        container = self.create_container_spec(task)
        
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={
                "task-id": task['_id'],
                "task-type": task.get('type', 'default')
            }),
            spec=client.V1PodSpec(
                restart_policy=task.get('restartPolicy', 'Never'),
                containers=[container],
                volumes=[self.create_volume_spec(v) for v in task['volumes']]
            )
        )

        return client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                labels={
                    "task-id": task['_id'],
                    "pipeline": "neuroimaging"
                }
            ),
            spec=client.V1JobSpec(
                backoff_limit=2,
                ttl_seconds_after_finished=86400,  # Automatically cleanup after 24 hours
                template=template
            )
        )

    def setup_change_stream(self):
        """Setup MongoDB change stream listener"""
        pipeline = [{
            '$match': {
                'operationType': {'$in': ['insert', 'update']},
                'fullDocument.status': 'pending'
            }
        }]
        
        try:
            return self.db.watch(pipeline=pipeline, full_document='updateLookup')
        except errors.PyMongoError as e:
            logger.error(f"Change stream connection failed: {str(e)}")
            raise

    def process_pending_tasks(self):
        """Process pending tasks using change stream"""
        try:
            with self.setup_change_stream() as stream:
                for change in stream:
                    if change['operationType'] == 'insert':
                        self.handle_task(change['fullDocument'])
                    elif change['operationType'] == 'update':
                        self.handle_task(change['fullDocument'])
        except Exception as e:
            logger.error(f"Change stream processing interrupted: {str(e)}")
            time.sleep(5)  # Wait before reconnecting

    def handle_task(self, task):
        """Handle single task"""
        try:
            # Auto-populate default values
            task.setdefault('resources', {}).setdefault('requests', {"cpu": "1", "memory": "2Gi"})
            task.setdefault('restartPolicy', 'Never')
            task['execution'].setdefault('command', [])
            task['execution'].setdefault('args', [])
            
            job_manifest = self.create_job_manifest(task)
            self.batch_api.create_namespaced_job(namespace="default", body=job_manifest)
            
            self.db.update_one(
                {"_id": task["_id"]},
                {"$set": {
                    "status": "running",
                    "k8s_job": job_manifest.metadata.name,
                    "start_time": datetime.utcnow().isoformat()
                }}
            )
            logger.info(f"Successfully created job for task {task['_id']}: {job_manifest.metadata.name}")
            
        except ApiException as api_e:
            error_msg = f"Kubernetes API error: {api_e.reason}"
            self.update_task_status(task['_id'], 'failed', error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error processing task: {str(e)}"
            self.update_task_status(task['_id'], 'failed', error_msg)
            logger.error(error_msg)

    def update_task_status(self, task_id, status, error_msg=None):
        """Update task status"""
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if error_msg:
            update_data["error"] = error_msg
            
        self.db.update_one(
            {"_id": task_id},
            {"$set": update_data}
        )

    def monitor_running_jobs(self):
        """Monitor running jobs status"""
        try:
            running_tasks = self.db.find({"status": "running"})
            for task in running_tasks:
                self.check_job_status(task)
        except Exception as e:
            logger.error(f"Error monitoring task status: {str(e)}")

    def check_job_status(self, task):
        """Check job status for a single task"""
        job_name = task.get('k8s_job')
        if not job_name:
            return

        try:
            job_status = self.batch_api.read_namespaced_job_status(
                name=job_name, 
                namespace="default"
            )
            
            if job_status.status.succeeded:
                self.update_task_status(task['_id'], 'completed')
                logger.info(f"Task {task['_id']} completed successfully")
            elif job_status.status.failed and job_status.status.failed >= job_status.spec.backoff_limit:
                self.update_task_status(task['_id'], 'failed', "Job failed beyond backoff limit")
                
        except ApiException as e:
            if e.status == 404:
                self.update_task_status(task['_id'], 'failed', "Associated Kubernetes job not found")
            else:
                logger.error(f"API error checking job status: {str(e)}")

    def run(self):
        """Main scheduler loop"""
        logger.info("Task scheduler starting")
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
            
        while True:
            try:
                self.process_pending_tasks()
                self.monitor_running_jobs()
                time.sleep(10)
            except KeyboardInterrupt:
                logger.info("Received termination signal, shutting down scheduler")
                break
            except Exception as e:
                logger.error(f"Unhandled exception in main loop: {str(e)}")
                time.sleep(30)

if __name__ == "__main__":
    scheduler = TaskScheduler()
    scheduler.run()
