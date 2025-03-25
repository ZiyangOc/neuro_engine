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

    def submit_k8s_job(self, manifest):
        print(manifest)
        pass

if __name__ == "__main__":
    processor = TaskProcessor()
    scheduler = BlockingScheduler()
    scheduler.add_job(processor.process_pending_tasks, 'interval', seconds=30)
    scheduler.start()