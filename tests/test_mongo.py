import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure
import os
import time
from dotenv import load_dotenv

load_dotenv()

# 根据环境自动选择MongoDB地址
MONGO_HOST = "localhost"
MONGO_URI = f"mongodb://appuser:appuser123@{MONGO_HOST}:27017/taskdb?authSource=admin&retryWrites=true&w=majority"

@pytest.fixture(scope='module')
def mongo_client():
    # 增加连接重试逻辑
    max_retries = 5
    for _ in range(max_retries):
        try:
            client = MongoClient(MONGO_URI)
            client.admin.command('ping')  # 测试连接是否有效
            break
        except Exception as e:
            time.sleep(2)
    else:
        pytest.fail("Could not connect to MongoDB after multiple attempts")

    # 显式创建索引
    db = client.taskdb
    db.tasks.create_index([("created_at", 1)], name="created_at_1")
    db.tasks.create_index([("status", 1)], name="status_1")
    
    yield client
    
    # 测试后清理
    db.tasks.delete_many({})
    client.close()

def test_insert_and_retrieve_task(mongo_client):
    db = mongo_client.taskdb
    tasks_collection = db.tasks

    task = {
        "name": "Test Task",
        "status": "pending",
        "created_at": "2024-03-24T00:00:00Z"
    }
    result = tasks_collection.insert_one(task)
    assert result.inserted_id is not None

    inserted_task = tasks_collection.find_one({"_id": result.inserted_id})
    assert inserted_task["name"] == task["name"]

def test_create_index(mongo_client):
    indexes = mongo_client.taskdb.tasks.index_information()
    
    # 检查索引是否存在
    assert "created_at_1" in indexes
    assert "status_1" in indexes
    
    # 验证索引字段正确性
    assert indexes["created_at_1"]["key"][0][0] == "created_at"
    assert indexes["status_1"]["key"][0][0] == "status"

def test_authentication():
    # 使用动态 HOST 变量
    invalid_password_uri = f"mongodb://appuser:wrongpass@{MONGO_HOST}:27017/taskdb?authSource=admin"
    invalid_authdb_uri = f"mongodb://appuser:appuser123@{MONGO_HOST}:27017/taskdb?authSource=wrongdb"

    # 增加重试机制
    try:
        MongoClient(invalid_password_uri, serverSelectionTimeoutMS=10000)
    except OperationFailure as e:
        assert "Authentication failed" in str(e)
    except Exception as e:
        pytest.fail(f"Expected OperationFailure, but got different exception: {e}")

    try:
        MongoClient(invalid_authdb_uri, serverSelectionTimeoutMS=10000)
    except OperationFailure as e:
        assert "Authentication failed" in str(e)
    except Exception as e:
        pytest.fail(f"Expected OperationFailure, but got different exception: {e}")