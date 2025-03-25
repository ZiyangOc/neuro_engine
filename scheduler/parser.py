from kubernetes import client, config
import json
import logging

logger = logging.getLogger(__name__)

def build_job_manifest(task_data):
    """Generate Kubernetes Job manifest from task data"""
    job_name = f"task-{task_data['_id']}"
    
    return client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="task-executor",
                            image=task_data["execution"]["containerImage"],
                            command=task_data["execution"].get("command"),
                            args=task_data.get("args"),
                            env=[
                                {"name": k, "value": v} 
                                for k, v in task_data.get("env", {}).items()
                            ]
                        )
                    ],
                    restart_policy="Never"
                )
            ),
            backoff_limit=3
        )
    )