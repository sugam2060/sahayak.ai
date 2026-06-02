from starlette.config import Config
from starlette.datastructures import Secret
import os

# Find the .env file in the root directory
# Assuming this file is in my-monorepo/shared/config.py
# Root is one level up from shared/
# 1. First, check if we are running inside Docker
if os.path.exists("/.dockerenv"):
    # Inside Docker, rely strictly on OS environment variables injected by Compose
    config = Config()
else:
    # Local fallback (running bare-metal via terminal)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # If running bare metal from root, .env is up one more level
    env_file = os.path.join(base_dir, "..", ".env") 
    if not os.path.exists(env_file):
        # Fallback to local directory if structure varies
        env_file = os.path.join(base_dir, ".env")
        
    config = Config(env_file if os.path.exists(env_file) else None)

# Database
DATABASE_URL = config("DATABASE_URL", default="postgresql+asyncpg://user:pass@localhost:5432/dbname")

# gRPC Service Addresses
AUTH_SERVICE_ADDR = config("AUTH_SERVICE_ADDR", default="localhost:50051")
CHATAI_SERVICE_ADDR = config("CHATAI_SERVICE_ADDR", default="localhost:50052")
WORKERS_SERVICE_ADDR = config("WORKERS_SERVICE_ADDR", default="localhost:50053")


# Gateway
GATEWAY_PORT = config("GATEWAY_PORT", cast=int, default=8000)
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")

# Mail
SMTP_HOST = config("SMTP_HOST", default="smtp.gmail.com")
SMTP_PORT = config("SMTP_PORT", cast=int, default=587)
SMTP_USER = config("SMTP_USER", default="")
SMTP_PASSWORD = config("SMTP_PASSWORD", default="")
MAIL_FROM = config("MAIL_FROM", default="no-reply@sahayak.com")
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
BACKEND_URL = config("BACKEND_URL", default="https://unoared-unpesterous-amir.ngrok-free.dev")

# JWT
JWT_SECRET = config("JWT_SECRET", default="your-secret-key")
JWT_ALGORITHM = config("JWT_ALGORITHM", default="HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", cast=int, default=60)
REFRESH_TOKEN_EXPIRE_DAYS = config("REFRESH_TOKEN_EXPIRE_DAYS", cast=int, default=30)

# Environment Configuration
APP_ENV = config("APP_ENV", default="development")

# Instagram / Facebook Configuration
INSTAGRAM_APP_ID = config("INSTAGRAM_APP_ID", default="")
INSTAGRAM_APP_SECRET = config("INSTAGRAM_APP_SECRET", default="")
INSTAGRAM_REDIRECT_URI = config("INSTAGRAM_REDIRECT_URI", default="https://api.sugampudasain.xyz/connectors/oauth/callback/instagram")
INSTAGRAM_WEBHOOK_TOKEN = config("INSTAGRAM_VERIFY_TOKEN", default="123456789")
INSTAGRAM_VERIFY_TOKEN = INSTAGRAM_WEBHOOK_TOKEN


# Telegram Configuration
TELEGRAM_API_BASE_URL = config("TELEGRAM_API_BASE_URL", default="https://api.telegram.org")

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = config("KAFKA_BOOTSTRAP_SERVERS", default="localhost:9092,localhost:9093,localhost:9094")
KAFKA_SECURITY_PROTOCOL = config("KAFKA_SECURITY_PROTOCOL", default="PLAINTEXT")
AWS_REGION = config("AWS_REGION", default="ap-south-1")

# MongoDB Configuration
MONGODB_URL = config("MONGODB_URL", default="mongodb+srv://sugam2060:XNCBD8sEsMceta6m@cluster0.fxcagu2.mongodb.net/")
MONGODB_DB_NAME = config("MONGODB_DB_NAME", default="sahayak_ai")

# Groq Configuration
GROQ_API_KEY = config("GROQ_API_KEY", default="")

# Pinecone Configuration
PINECONE_API_KEY = config("PINECONE_API_KEY", default="")
PINECONE_INDEX_HOST = config("PINECONE_INDEX_HOST", default="")

# Cloudinary
CLOUDINARY_CLOUD_NAME = config("CLOUDINARY_CLOUD_NAME", default="dqalfkroo")
CLOUDINARY_API_KEY = config("CLOUDINARY_API_KEY", default="132545484359525")
CLOUDINARY_API_SECRET = config("CLOUDINARY_API_SECRET", default="HUcNQXY96H_al0vqhqArwo_Lh7s")




