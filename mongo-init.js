// Read password from Docker secret
const rootPass = process.env.MONGO_INITDB_ROOT_PASSWORD;
const appPass = require('fs').readFileSync('/run/secrets/mongo_app_password', 'utf8').trim();

db = db.getSiblingDB('neuro');
db.createUser({
  user: process.env.MONGO_USER,
  pwd: appPass,
  roles: [{ role: 'readWrite', db: 'neuro' }]
});
