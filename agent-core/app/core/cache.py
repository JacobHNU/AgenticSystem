import json
import redis.asyncio as redis
from typing import Optional, Any


class Cache:
    """Redis cache manager"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, ttl: int = 3600):
        self.host = host
        self.port = port
        self.db = db
        self.ttl = ttl
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        self.client = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)

    async def close(self):
        if self.client:
            await self.client.close()

    async def get(self, key: str) -> Optional[Any]:
        raw = await self.client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int = None):
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        await self.client.set(key, serialized, ex=ttl or self.ttl)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(key))

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False
