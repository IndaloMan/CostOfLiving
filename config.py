import os
from dotenv import load_dotenv

load_dotenv()

APP_VERSION = "1.12"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
RECEIPTS_FOLDER = os.path.join(BASE_DIR, "Receipts")
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
MAX_UPLOAD_SIZE_MB = 20
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
