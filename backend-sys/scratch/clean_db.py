import asyncio
from sqlalchemy import text
from shared.database.engine import engine

async def clean_db():
    async with engine.begin() as conn:
        print("Cleaning organizations...")
        await conn.execute(text("DELETE FROM organizations"))
        print("Done.")

if __name__ == "__main__":
    asyncio.run(clean_db())
