import asyncio
from sqlalchemy import text
from shared.database.engine import engine

async def check_db():
    async with engine.connect() as conn:
        # Check data
        r1 = await conn.execute(text("SELECT id, name, owner_id FROM organizations"))
        orgs = r1.fetchall()
        print("\n--- Organizations ---")
        for org in orgs:
            print(f"ID: {org[0]}, Name: {org[1]}, Owner: {org[2]}")
            
        r2 = await conn.execute(text("SELECT id, full_name, email FROM users"))
        users = r2.fetchall()
        print("\n--- Users ---")
        for user in users:
            print(f"ID: {user[0]}, Name: {user[1]}, Email: {user[2]}")

if __name__ == "__main__":
    asyncio.run(check_db())
