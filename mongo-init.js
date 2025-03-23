// Read password from Docker secret
const rootPass = process.env.MONGO_INITDB_ROOT_PASSWORD;
const appPass = 'mongopass';

db = db.getSiblingDB('neuro');
db.createUser({
  user: "admin",
  pwd: passwordPrompt(), // Will use the secret from docker-compose
  roles: ["readWrite"]
});
