import os
from pymongo import MongoClient

# Connessione a MongoDB
mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")  # Connessione predefinita per debug
print(mongo_url)
client = MongoClient(mongo_url)
db = client["15MinutiDB"]
