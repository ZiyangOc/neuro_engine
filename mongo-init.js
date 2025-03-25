// mongo-init.js

// 创建应用用户（认证数据库为 admin）
db.getSiblingDB("admin").createUser({
  user: "appuser",
  pwd: "appuser123",
  roles: [ 
    { role: "readWrite", db: "taskdb" }  // 授权 taskdb 的读写权限
  ]
});

// --------------- 关键修正：切换到 taskdb 创建索引 ---------------
const taskdb = db.getSiblingDB("taskdb");

// 创建集合（可选，MongoDB 会在首次插入数据时自动创建集合）
taskdb.createCollection("tasks");

// 创建索引
taskdb.tasks.createIndex({ created_at: 1 });
taskdb.tasks.createIndex({ status: 1 });