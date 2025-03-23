import requests
import json
import os

API_ENDPOINT = os.environ.get('API_ENDPOINT', 'http://localhost:5000/api/tasks')

SAMPLE_TASK = {
    "metadata": {
        "name": "BNA Atlas处理任务",
        "description": "处理被试sub-001的BNA图谱分析",
        "tags": ["fMRI", "BNA", "preprocessing"]
    },
    "data": {
        "input": {
            "subject_id": "sub-001",
            "atlas": "BNA_v3"
        },
        "output": {
            "path": "/data/output/sub-001",
            "formats": ["NIFTI", "CSV"]
        }
    },
    "execution": {
        "containerImage": "nipreps/fmriprep:24.0.0",
        "resources": {
            "cpu": 4,
            "memory": "16Gi"
        }
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
