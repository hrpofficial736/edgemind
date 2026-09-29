import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("EDGE_DATA_DIR", BASE_DIR / "data"))
SHARD_DIR = DATA_DIR / "shard"
DB_PATH = DATA_DIR / "ledger.db"
MODEL_DIR = BASE_DIR / "models"

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384
VECTOR_NAME = "memory"

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = "memories"

DEVICE_ID = "device-a"          # this laptop
REMOTE_DEVICE_ID = "device-b"   # the simulated "other device"

# Memories containing these words never leave the device unless the user says so.
SENSITIVE_KEYWORDS = ["password", "passcode", "pin", "otp", "secret",
                      "api key", "credential", "gate code", "token"]
