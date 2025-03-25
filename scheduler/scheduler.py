from pymongo import MongoClient
from apscheduler.schedulers.blocking import BlockingScheduler
import os
import logging
from parser import build_job_manifest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskProcessor:
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client.taskdb
        self.task_collection = self.db.tasks
        
    def process_pending_tasks(self):
        """Fetch and process pending tasks from MongoDB"""
        pending_tasks = self.task_collection.find({"status": "pending"})
        for task in pending_tasks:
            try:
                job_manifest = build_job_manifest(task)
                self.submit_k8s_job(job_manifest)
                self.task_collection.update_one(
                    {"_id": task["_id"]},
                    {"$set": {"status": "processing"}}
                )
                logger.info(f"Processed task {task['_id']}")
            except Exception as e:
                logger.error(f"Failed processing task {task['_id']}: {str(e)}")

    def submit_k8s_job(self, job) -> str:
        """提交Kubernetes Job并返回作业ID"""
        from kubernetes import client, config
        from kubernetes.client.rest import ApiException
        import socket
        
        try:
            # 自动检测环境加载配置
            try:
                config.load_incluster_config()  # 集群内部认证
            except config.ConfigException:
                # 添加详细的路径检查和日志记录
                kube_config = os.path.expanduser("~/.kube/config")
                minikube_ca = "/root/.minikube/ca.crt"  # 容器内挂载路径
                
                if not os.path.exists(kube_config):
                    raise RuntimeError(f"Kube config file not found at {kube_config}")
                if not os.path.exists(minikube_ca):
                    raise RuntimeError(f"Minikube CA cert not found at {minikube_ca}")
                    
                logging.info(f"Loading kube config from {kube_config}")
                logging.info(f"Using Minikube CA cert at {minikube_ca}")
                
                config.load_kube_config(config_file=kube_config)  # 显式指定配置文件路径

            api = client.BatchV1Api()
    
            # 提交Job
            job = api.create_namespaced_job(
                namespace="default",
                body=job
            )
            
            logger.info(f"Submitted job {job.metadata.name}")
            return job.metadata.name
            
        except ApiException as e:
            logger.error(f"K8s API error: {e.reason} ({e.status})")
            raise
        except socket.error as e:
            logger.critical(f"Network error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

if __name__ == "__main__":
    processor = TaskProcessor()
    scheduler = BlockingScheduler()
    scheduler.add_job(processor.process_pending_tasks, 'interval', seconds=30)
    scheduler.start()