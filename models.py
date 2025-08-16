from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base, Database
from datetime import datetime
import asyncio
import pytz

def get_current_utc_time():
    """
    Sistemin yerel saat ayarlarından bağımsız olarak, 
    mevcut UTC zamanını döndürür.
    """
    return datetime.utcnow().replace(tzinfo=pytz.utc)

istanbul_tz = pytz.timezone('Europe/Istanbul')

class User(Base):
    """
    Kullanıcılar için veritabanı tablosunu temsil eden model.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    is_email_validation = Column(Boolean, default=False)
    role_id = Column(Integer, default=1)
    created_date = Column(DateTime(timezone=True), default=lambda: get_current_utc_time())
    updated_date = Column(DateTime(timezone=True), default=lambda: get_current_utc_time())

    # User-ValidationEmailLog ilişkisini tanımla.
    # back_populates değeri "user" olarak kalacak.
    validation_email_logs = relationship("ValidationEmailLog", back_populates="user")

    # Kullanıcının gönderdiği mesajlar
    sent_messages = relationship("Message", foreign_keys="[Message.sender_id]", back_populates="sender")
    # Kullanıcının aldığı mesajlar

    received_messages = relationship("Message", foreign_keys="[Message.receiver_id]", back_populates="receiver")



class ValidationEmailLog(Base):
    """
    Gönderilen doğrulama e-postalarının loglarını tutar.
    """
    __tablename__ = "validation_email_log"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    is_success = Column(Boolean)
    type=Column(String)
    sent_date = Column(DateTime(timezone=True), default=lambda: get_current_utc_time())
    
    # relationship adını "user" olarak belirle ve back_populates'i "validation_email_logs" olarak değiştir.
    user = relationship("User", back_populates="validation_email_logs")

class Message(Base):
    """
    Kullanıcılar arasındaki mesajları saklamak için veritabanı modeli.
    """
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    receiver_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content = Column(String, nullable=False)
    sent_date = Column(DateTime(timezone=True), default=lambda: get_current_utc_time())
    is_read = Column(Boolean, default=False)
    
    # Mesajı gönderen kullanıcıya referans
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    # Mesajı alan kullanıcıya referans
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")


# db = Database()
# async def main():
#     await db.init_db()

# asyncio.run(main())

    

