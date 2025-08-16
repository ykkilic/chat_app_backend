from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import AsyncGenerator
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Database:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.engine: AsyncEngine = create_async_engine(self.database_url)
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            # Tabloları oluştur
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session() as session:
            yield session
