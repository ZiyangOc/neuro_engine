# task_configurator.py
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TaskValidator:
    @staticmethod
    def validate(task_data: Dict[str, Any]):
        """验证任务数据结构有效性"""
        if not task_data.get("execution"):
            raise ValueError("Execution configuration is required")
        
        execution = task_data["execution"]
        if not execution.get("containerImage"):
            raise ValueError("containerImage is required")
        if not execution.get("command"):
            raise ValueError("command is required")
        
        # 可扩展其他验证规则
        if not isinstance(execution.get("command", []), list):
            raise ValueError("Command must be a list")
        
        logger.debug("Task data validation passed")

class TaskDocumentBuilder:
    @staticmethod
    def build(
        task_id: str,
        task_data: Dict[str, Any],
        default_timeout: int,
        default_max_retries: int
    ) -> Dict[str, Any]:
        """构建标准化任务文档结构"""
        return {
            "_id": task_id,
            "status": "pending",
            "created_at": datetime.utcnow(),
            "priority": task_data.get("priority", "normal"),
            "timeout": task_data.get("timeout", default_timeout),
            "max_retries": task_data.get("max_retries", default_max_retries),
            "attempts": 0,
            "execution": task_data["execution"],
            "metadata": task_data.get("metadata", {}),
            "input": task_data.get("input"),
            "output": task_data.get("output")
        }

class KubernetesJobBuilder:
    @staticmethod
    def build_manifest(
        task_id: str,
        task_execution: Dict[str, Any],
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """构建Kubernetes Job配置清单"""
        job_name = f"task-{task_id[:8]}"
        
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": namespace
            },
            "spec": {
                "backoffLimit": task_execution.get("max_retries", 3),
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "task-executor",
                            "image": task_execution["containerImage"],
                            "command": task_execution["command"],
                            "args": task_execution.get("args"),
                            "env": [
                                {"name": k, "value": v}
                                for k, v in task_execution.get("env", {}).items()
                            ],
                            "resources": task_execution.get("resources", {}),
                            "volumeMounts": [
                                {"name": vol["name"], "mountPath": vol["mountPath"]}
                                for vol in task_execution.get("volumeMounts", [])
                            ]
                        }],
                        "restartPolicy": "Never",
                        "volumes": [
                            {
                                "name": vol["name"],
                                "hostPath": {"path": vol["hostPath"]}
                            }
                            for vol in task_execution.get("volumes", [])
                        ]
                    }
                }
            }
        }