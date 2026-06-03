import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from shared.database.engine import SessionLocal
from shared.database.schema.platform_connectors import PlatformConnector

async def main():
    async with SessionLocal() as session:
        stmt = select(PlatformConnector)
        res = await session.execute(stmt)
        connectors = res.scalars().all()
        print("Platform Connectors:")
        for c in connectors:
            print(f"ID: {c.id}, Business: {c.business_id}, Platform: {c.platform}, Platform Account ID: {c.platform_account_id}, Account Name: {c.platform_account_name}, Status: {c.status}")

if __name__ == "__main__":
    asyncio.run(main())
