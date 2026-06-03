import asyncmy
from asyncmy.pool import Pool
from typing import Optional, Dict, Any, List


class Database:
    """MySQL connection pool manager"""

    def __init__(self, host: str, port: int, database: str, user: str, password: str, pool_size: int = 10):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool_size = pool_size
        self.pool: Optional[Pool] = None

    @property
    def dsn(self) -> str:
        return f"mysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    async def connect(self):
        self.pool = await asyncmy.create_pool(
            host=self.host, port=self.port,
            user=self.user, password=self.password,
            database=self.database, minsize=1, maxsize=self.pool_size
        )

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def execute(self, sql: str, params: tuple = None) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                await conn.commit()
                return cur.rowcount

    async def fetchone(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchone()

    async def fetchall(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(asyncmy.cursors.DictCursor) as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()
