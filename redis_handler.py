import redis.asyncio as redis
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

class RedisHandler:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL")
        self.redis = redis.from_url(self.redis_url)

    async def connect(self):
        # redis-py async client otomatik bağlanıyor, genelde gerekmez
        pass

    async def close(self):
        await self.redis.close()

    async def set(self, key: str, value: str, expire_seconds: Optional[int] = None):
        """
        Redis'e veri atar.
        :param key: Anahtar
        :param value: Değer (string olarak)
        :param expire_seconds: Kaç saniye sonra silineceği (TTL). None ise süresiz.
        """
        await self.redis.set(key, value, ex=expire_seconds)

    async def get(self, key: str) -> Optional[str]:
        """
        Redis'ten veri alır.
        :param key: Anahtar
        :return: Değer veya None
        """
        value = await self.redis.get(key)
        if value is not None:
            return value.decode('utf-8')
        return None
    
    async def delete(self, key: str) -> int:
        """
        Redis'ten anahtarı siler.
        :param key: Silinecek anahtar
        :return: Silinen anahtar sayısı (0 veya 1)
        """
        result = await self.redis.delete(key)
        return result
