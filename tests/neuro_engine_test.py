import unittest
import requests
import uuid
import json

class TestTaskAPI(unittest.TestCase):
    API_BASE_URL = "http://localhost:5001/api"  # 根据实际API地址调整
    TASKS_ENDPOINT = f"{API_BASE_URL}/tasks"

    def setUp(self):
        self.session = requests.Session()
        self.test_task_id = str(uuid.uuid4())
        self.headers = {"Content-Type": "application/json"}

    def test_create_task_with_volume(self):
        """测试带存储卷配置的任务创建"""
        payload = {
            "execution": {
                "containerImage": "busybox",
                "command": ["sh", "-c", "echo 'Hello World' > /output/helloworld.txt && ls -l /output"],
                "volumes": [
                {
                    "name": "output-volume",
                    "mountPath": "/output",
                    "type": "hostPath",
                    "source": {
                    "path": "/home/data2/ziyang_project/neuro_engine/tests",
                    "type": "DirectoryOrCreate"  
                    }
                }
                ]
            },
            "metadata": {
                "description": "Test task - Create hello world file with hostPath volume"
            }
            }

        response = self.session.post(
            self.TASKS_ENDPOINT,
            data=json.dumps(payload),
            headers=self.headers
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("task_id", response.json())


    def tearDown(self):
        self.session.close()

if __name__ == "__main__":
    unittest.main()