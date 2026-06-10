import logging
from motor.motor_asyncio import AsyncIOMotorClient
from shared.config import MONGODB_URL, MONGODB_DB_NAME

logger = logging.getLogger(__name__)

class MongoDBManager:
    _client: AsyncIOMotorClient = None
    _db = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        if cls._client is None:
            logger.info("Initializing MongoDB client...")
            cls._client = AsyncIOMotorClient(MONGODB_URL)
        return cls._client

    @classmethod
    def get_db(cls):
        if cls._db is None:
            client = cls.get_client()
            cls._db = client[MONGODB_DB_NAME]
        return cls._db

    @classmethod
    async def close(cls):
        if cls._client:
            logger.info("Closing MongoDB connection client...")
            cls._client.close()
            cls._client = None
            cls._db = None

async def init_mongodb_db():
    """
    Initializes database indexes for the MongoDB collections.
    Creates a unique index on platform and user.sender_id to satisfy
    'one document for one sender_id and platform'.
    """
    try:
        db = MongoDBManager.get_db()
        # Create unique compound index on 'platform' and 'user.sender_id'
        logger.info("Creating unique index on 'conversations' collection...")
        index_name = await db.conversations.create_index(
            [("platform", 1), ("user.sender_id", 1)],
            unique=True
        )
        logger.info(f"Successfully created unique index '{index_name}' on 'conversations' collection.")
        
        # Additional helper index for organization lookups
        org_index_name = await db.conversations.create_index(
            [("organization_id", 1)]
        )
        logger.info(f"Successfully created index '{org_index_name}' on 'conversations' collection.")

        # Create indexes for 'internal_conversations'
        logger.info("Creating indexes on 'internal_conversations' collection...")
        internal_org_type_idx = await db.internal_conversations.create_index(
            [("organization_id", 1), ("type", 1)]
        )
        logger.info(f"Successfully created index '{internal_org_type_idx}' on 'internal_conversations'.")

        internal_user_ids_idx = await db.internal_conversations.create_index(
            [("user_ids", 1)]
        )
        logger.info(f"Successfully created index '{internal_user_ids_idx}' on 'internal_conversations'.")
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB indexes: {str(e)}")
        raise e

