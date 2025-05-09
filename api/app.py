from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
import uuid
from datetime import datetime

app = Flask(__name__)

mongo_uri = f"mongodb://appuser:appuser123@mongo:27017/taskdb?authSource=admin"
client = MongoClient(mongo_uri)
db = client['taskdb']
tasks = db['tasks']

@app.route('/api/tasks', methods=['POST'])
def create_task():
    task_data = request.json
    
    task_id = str(uuid.uuid4())
    task_data['_id'] = task_id
    task_data['status'] = 'pending'
    task_data['created_at'] = datetime.utcnow().isoformat()
    task_data['updated_at'] = datetime.utcnow().isoformat()
    
    tasks.insert_one(task_data)
    
    return jsonify({"task_id": task_id, "status": "pending"})

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    result = []
    for task in tasks.find({}, {'_id': 1, 'status': 1, 'created_at': 1}):
        task['_id'] = str(task['_id'])
        result.append(task)
    return jsonify(result)

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = tasks.find_one({'_id': task_id})
    if task:
        task['_id'] = str(task['_id'])
        return jsonify(task)
    return jsonify({"error": "Task not found"}), 404

