import os
from pathlib import Path

from pymongo import MongoClient


def _load_env_file():
	env_path = Path(__file__).resolve().parents[1] / ".env"
	if not env_path.exists():
		return

	for raw_line in env_path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue

		key, value = line.split("=", 1)
		os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

# Connessione a MongoDB
mongo_url = (
	os.getenv("MONGO_URL")
	or os.getenv("MONGO_URL_LOCAL")
	or os.getenv("MONGO_URL_DOCKER")
	or "mongodb://user:pass@mongodb:27017"
)
client = MongoClient(mongo_url)
db = client[os.getenv("MONGO_DB", "15minute")]
