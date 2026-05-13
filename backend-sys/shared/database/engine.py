from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from shared.config import DATABASE_URL

# Scalable Engine with Connection Pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for debugging SQL
    pool_size=20,           # Number of permanent connections
    max_overflow=10,        # Additional temporary connections
    pool_timeout=30,        # Seconds to wait for a connection
    pool_recycle=1800,      # Recycle connections every 30 minutes
    pool_pre_ping=True,     # Check connection health before use
)

# Async Session Factory
SessionLocal = async_sessionmaker(
    bind=engine, 
    expire_on_commit=False,
    autoflush=False
)
