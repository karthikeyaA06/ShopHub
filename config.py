import os
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables, if the file exists

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-this-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "shophub.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    BILLS_FOLDER = os.path.join(BASE_DIR, "static", "bills")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB uploads

    # Admin bootstrap credentials (used only the very first time the DB is created)
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@shophub.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")

    # Razorpay (optional - fill in your own test/live keys to enable real gateway init)
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
