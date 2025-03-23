import requests
import json
import os

API_ENDPOINT = os.environ.get('API_ENDPOINT', 'http://localhost:5000/api/tasks')

SAMPLE_TASK = {
    "metadata": {
        "name": "简单测试任务",
        "description": "运行一个简单的测试命令",
        "tags": ["test", "simple"]
    },
    "data": {
        "input": {},
        "output": {
            "path": "/data/output",
            "formats": ["txt"]
        }
    },
    "execution": {
        "containerImage": "alpine:latest",
        "resources": {
            "cpu": 1,
            "memory": "512Mi"
        },
        "command": ["echo", "Hello, World!"]
    }
}

def submit_sample_task():
    try:
        response = requests.post(
            API_ENDPOINT,
            json=SAMPLE_TASK,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        print("任务提交成功:")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"任务提交失败: {str(e)}")

def list_all_tasks():
    try:
        response = requests.get(API_ENDPOINT)
        response.raise_for_status()
        print("\n当前所有任务:")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"获取任务列表失败: {str(e)}")

if __name__ == "__main__":
    submit_sample_task()
    list_all_tasks()
