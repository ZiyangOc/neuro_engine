// 从Docker secrets读取密码
var rootPass = cat('/run/secrets/mongo_root_password');
var appPass = cat('/run/secrets/mongo_app_password');

// 创建应用数据库和用户
db = db.getSiblingDB('taskdb');
db.createUser({
  user: "appuser",
  pwd: appPass,
  roles: [{
    role: "readWrite",
    db: "taskdb"
  }]
});

// 创建任务集合索引
db.tasks.createIndex({ created_at: 1 });
db.tasks.createIndex({ status: 1 });
