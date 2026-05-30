from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, Field
import hashlib
import re
import asyncio

import cloudinary
import cloudinary.uploader

from shared.database.engine import SessionLocal
from shared.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
from shared.database.schema.products import Product
from shared.database.mongodb import MongoDBManager

# Configure Cloudinary SDK
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

async def get_db():
    async with SessionLocal() as session:
        yield session

# FastAPI UploadFile Cloudinary Upload Utility
async def upload_cloudinary_image(
    upload_file: UploadFile,
    org_id: str,
    org_name: str
) -> str:
    file_bytes = await upload_file.read()
    url = await upload_cloudinary_image_bytes(file_bytes, upload_file.filename or "", upload_file.content_type or "", org_id, org_name)
    await upload_file.seek(0)
    return url

# Raw Bytes Cloudinary Upload Utility (used by gRPC)
async def upload_cloudinary_image_bytes(
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    org_id: str,
    org_name: str
) -> str:
    safe_org_name = re.sub(r'[^a-zA-Z0-9_]', '_', org_name).lower()
    folder_path = f"sahayak/{safe_org_name}_{org_id}"
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    async with SessionLocal() as db_session:
        from sqlalchemy import select
        stmt = select(Product.image).where(Product.image.like(f"%/{file_hash}.%"))
        res = await db_session.execute(stmt)
        existing_sql_img = res.scalars().first()
        if existing_sql_img:
            return existing_sql_img

    try:
        mongo_db = MongoDBManager.get_db()
        conv = await mongo_db.conversations.find_one({
            "messages.image_url": {"$regex": f"/{file_hash}\\."}
        })
        if conv:
            for msg in conv.get("messages", []):
                img_url = msg.get("image_url")
                if img_url and f"/{file_hash}." in img_url:
                    return img_url
    except Exception as e:
        print("Error checking MongoDB for duplicate image:", e)

    result = await asyncio.to_thread(
        cloudinary.uploader.upload,
        file_bytes,
        folder=folder_path,
        public_id=file_hash
    )
    return result.get("secure_url")

# Cloudinary Deletion Utility
async def delete_cloudinary_image(image_url: str):
    await delete_cloudinary_image_task(image_url)

# Cloudinary Safe Delete Task (used by gRPC & tasks)
async def delete_cloudinary_image_task(image_url: str):
    if not image_url or "res.cloudinary.com" not in image_url:
        return
    try:
        parts = image_url.split("/image/upload/")
        if len(parts) < 2:
            return
        path_after_upload = parts[1]
        path_parts = path_after_upload.split("/")
        if path_parts[0].startswith("v") and path_parts[0][1:].isdigit():
            path_parts = path_parts[1:]
        public_id = "/".join(path_parts).rsplit(".", 1)[0]
        file_hash = public_id.split("/")[-1]

        async with SessionLocal() as db_session:
            from sqlalchemy import select
            stmt = select(Product.id).where(Product.image.like(f"%/{file_hash}.%"))
            res = await db_session.execute(stmt)
            if len(res.scalars().all()) > 0:
                print(f"Cloudinary image deletion skipped: referenced in SQL products ({public_id})")
                return

        try:
            mongo_db = MongoDBManager.get_db()
            conv = await mongo_db.conversations.find_one({
                "messages.image_url": {"$regex": f"/{file_hash}\\."}
            })
            if conv:
                print(f"Cloudinary image deletion skipped: referenced in MongoDB messages ({public_id})")
                return
        except Exception as e:
            print("Error checking MongoDB references before deletion:", e)

        result = await asyncio.to_thread(cloudinary.uploader.destroy, public_id)
        print(f"Cloudinary destroy result: {result}")
    except Exception as e:
        print(f"Exception during Cloudinary image deletion: {str(e)}")

# Pydantic Schemas
class ProductCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    price: int = Field(..., description="Price in cents/subunits")
    currency: str = Field(default="NPR", max_length=10)
    stock: int = Field(default=0)
    sku: Optional[str] = Field(None, max_length=100)
    image: Optional[str] = Field(None, max_length=255)
    is_active: bool = Field(default=True)
    metadata_json: Optional[dict] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    price: Optional[int] = None
    currency: Optional[str] = Field(None, max_length=10)
    stock: Optional[int] = None
    sku: Optional[str] = Field(None, max_length=100)
    image: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    metadata_json: Optional[dict] = None

def rc4_crypt(data: bytes, key: bytes) -> bytes:
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    
    i = 0
    j = 0
    out = bytearray()
    for char in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        k = S[(S[i] + S[j]) % 256]
        out.append(char ^ k)
    return bytes(out)

import base64

def encrypt_token(org_id: str, order_id: str, secret: str) -> str:
    plain = f"{org_id}:{order_id}".encode("utf-8")
    key = secret.encode("utf-8")
    enc = rc4_crypt(plain, key)
    return base64.urlsafe_b64encode(enc).decode("utf-8").replace("=", "")

def decrypt_token(token: str, secret: str) -> tuple[str, str]:
    missing_padding = len(token) % 4
    if missing_padding:
        token += "=" * (4 - missing_padding)
    enc = base64.urlsafe_b64decode(token.encode("utf-8"))
    key = secret.encode("utf-8")
    plain = rc4_crypt(enc, key).decode("utf-8")
    org_id, order_id = plain.split(":", 1)
    return org_id, order_id

