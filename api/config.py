import os
import logging
from pymongo import MongoClient, errors

logger = logging.getLogger(__name__)

class Config:
    """统一配置管理类"""
    def __init__(self):
        deploy_mode = os.getenv('DEPLOY_MODE', 'k8s')
        # 统一从Secret文件读取凭证
        with open('/run/secrets/mongo_root_password') as f:
            root_pass = f.read().strip()
        with open('/run/secrets/mongo_app_password') as f:
            app_pass = f.read().strip()
            
        self.mongo_uri = f"mongodb://app_user:{app_pass}@mongodb:27017/neuro?authSource=admin&replicaSet=rs0"
        self.api_port = int(os.getenv('API_PORT', 5000))
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
    def get_mongo_client(self, retries=3, delay=2):
        """获取MongoDB连接（带重试机制）"""
        for attempt in range(retries):
            try:
                client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
                client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
                return client
            except errors.PyMongoError as e:
                logger.error(f"MongoDB连接失败 (尝试 {attempt+1}/{retries}): {str(e)}")
                if attempt < retries - 1:
                    time.sleep(delay)
        raise RuntimeError("无法连接到MongoDB")
