import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime
import pytz
from models import Base, User, Message # Modellerinizi import ettiğinizden emin olun
import os
from dotenv import load_dotenv

load_dotenv()

# Veritabanı bağlantı bilgilerini buraya girin
DATABASE_URL = os.getenv("DATABASE_URL")

# Asenkron bir engine oluştur
engine = create_async_engine(DATABASE_URL, echo=True)

async def async_main():
    """
    Veritabanı tablolarına örnek veriler ekler.
    """
    # Oturum sınıfını oluştur
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with engine.begin() as conn:
        # Tabloları oluştur (eğer yoksa)
        await conn.run_sync(Base.metadata.create_all)

    # Veri ekleme işlemi
    async with async_session() as session:
        try:
            # Örnek kullanıcıları ekle
            user1 = User(
                username='alice',
                email='alice@example.com',
                password='hashed_password_alice'
            )
            user2 = User(
                username='bob',
                email='bob@example.com',
                password='hashed_password_bob'
            )
            user3 = User(
                username='charlie',
                email='charlie@example.com',
                password='hashed_password_charlie'
            )
            session.add_all([user1, user2, user3])
            await session.commit()
            
            # Commit işleminden sonra, nesnelerin ID'leri oluşur.
            # Nesneleri tekrar çekerek ID'lerini al
            alice = (await session.execute(select(User).filter_by(username='alice'))).scalar_one()
            bob = (await session.execute(select(User).filter_by(username='bob'))).scalar_one()
            charlie = (await session.execute(select(User).filter_by(username='charlie'))).scalar_one()

            # Örnek mesajları ekle
            messages = [
                # Alice ve Bob arasındaki sohbet
                Message(sender_id=alice.id, receiver_id=bob.id, content='Merhaba Bob! Nasılsın?'),
                Message(sender_id=bob.id, receiver_id=alice.id, content='İyiyim Alice, teşekkürler. Sen nasılsın?'),
                Message(sender_id=alice.id, receiver_id=bob.id, content='Ben de iyiyim, çok sağ ol.'),

                # Bob ve Charlie arasındaki sohbet (Okunmamış mesajlar)
                Message(sender_id=charlie.id, receiver_id=bob.id, content='Selam Bob, müsait misin?'),
                Message(sender_id=charlie.id, receiver_id=bob.id, content='Sana bir şey danışmak istiyorum.'),
                Message(sender_id=charlie.id, receiver_id=bob.id, content='Görünüşe göre meşgulsün, sonra konuşuruz.'),
            ]
            session.add_all(messages)
            await session.commit()
            
            print("Veritabanına örnek veriler başarıyla eklendi.")
            
        except Exception as e:
            await session.rollback() # Hata durumunda işlemi geri al
            print(f"Bir hata oluştu: {e}")
            
    await engine.dispose() # Engine'i kapat

if __name__ == '__main__':
    asyncio.run(async_main())