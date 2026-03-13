import os
from dotenv import load_dotenv

load_dotenv()

APP_VERSION = "1.48"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
RECEIPTS_FOLDER = os.path.join(BASE_DIR, "Receipts")
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
MAX_UPLOAD_SIZE_MB = 20
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

# Session secret key — set a stable value in .env for production
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-me-in-production")

# Admin shopper — seeded on first run; override via .env
ADMIN_EMAIL     = os.getenv("ADMIN_EMAIL",     "admin@example.com")
ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "Administrator")
ADMIN_NICKNAME  = os.getenv("ADMIN_NICKNAME",  "Admin")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD",  "changeme")

# Email (Flask-Mail via Gmail SMTP) — set in .env to enable
MAIL_SERVER   = os.getenv('MAIL_SERVER',   'smtp.gmail.com')
MAIL_PORT     = int(os.getenv('MAIL_PORT', '587'))
MAIL_USE_TLS  = os.getenv('MAIL_USE_TLS',  'true').lower() == 'true'
MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
MAIL_ENABLED  = bool(MAIL_USERNAME and MAIL_PASSWORD)
