import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy import text
from shared.database.engine import engine

async def check_db():
    async with engine.connect() as conn:
        try:
            r = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
            tables = [row[0] for row in r.fetchall()]
            print("--- Tables ---")
            print(tables)

            for t in ["platforms", "platform_connectors"]:
                print(f"\n--- {t} Columns ---")
                col_r = await conn.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{t}'"))
                cols = col_r.fetchall()
                for c in cols:
                    print(f"  {c[0]} ({c[1]})")
        except Exception as e:
            print(f"Error checking DB schema: {e}")





    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_db())
