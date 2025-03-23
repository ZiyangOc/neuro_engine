// Initialize application database and user
db = db.getSiblingDB('neuro_engine');
db.createUser({
  user: "app_user",
  pwd: "mongopass", // 密码应与docker-compose中api服务的MONGO_URI配置一致
  roles: [{
    role: "readWrite",
    db: "neuro_engine"
  }]
});
