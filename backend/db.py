import os
from pymongo import MongoClient

# Connessione a MongoDB
mongo_url = os.getenv("MONGO_URL", "mongodb://user:pass@localhost:27017")  # Connessione predefinita per debug
client = MongoClient(mongo_url)
db = client["15minute"]
