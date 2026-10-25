import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cloud-storage-secret-key-2026-academic-key-10938")
    
    # Database Configuration
    DATABASE_PATH = BASE_DIR / "instance" / "cloud_storage.db"
    
    # Local Storage Configuration
    UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
    
    # Maximum single file upload size (default 25MB)
    MAX_CONTENT_LENGTH_MB = int(os.getenv("MAX_CONTENT_LENGTH_MB", "25"))
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024
    
    # Per-user storage quota (default 100MB)
    USER_STORAGE_QUOTA_MB = int(os.getenv("USER_STORAGE_QUOTA_MB", "100"))
    USER_STORAGE_QUOTA_BYTES = USER_STORAGE_QUOTA_MB * 1024 * 1024
    
    # Storage Backend Mode: 'local' (prototype) or 's3' (AWS S3 Cloud Storage)
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
    
    # AWS S3 Cloud Configuration
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    
    # Allowed File Extensions
    ALLOWED_EXTENSIONS = {
        # Documents
        'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'csv', 'tsv',
        'xls', 'xlsx', 'ppt', 'pptx', 'md',
        # Images
        'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico',
        # Audio / Video
        'mp3', 'wav', 'ogg', 'mp4', 'webm', 'mkv',
        # Archives
        'zip', 'rar', '7z', 'tar', 'gz',
        # Code & Data
        'json', 'xml', 'html', 'css', 'js', 'py', 'sql', 'yaml', 'yml'
    }

    # Category classification for dashboard filtering and metrics
    CATEGORY_MAPPING = {
        'images': {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico'},
        'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'csv', 'tsv', 'xls', 'xlsx', 'ppt', 'pptx', 'md'},
        'media': {'mp3', 'wav', 'ogg', 'mp4', 'webm', 'mkv'},
        'archives': {'zip', 'rar', '7z', 'tar', 'gz'},
        'code': {'json', 'xml', 'html', 'css', 'js', 'py', 'sql', 'yaml', 'yml'}
    }

    @classmethod
    def get_file_category(cls, filename: str) -> str:
        if '.' not in filename:
            return 'others'
        ext = filename.rsplit('.', 1)[1].lower()
        for category, extensions in cls.CATEGORY_MAPPING.items():
            if ext in extensions:
                return category
        return 'others'
