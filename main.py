from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import User, ValidationEmailLog, Message
from database import Database
from redis_handler import RedisHandler
from email_handler import send_email_smtp
from middleware import AuthMiddleware
import random
from datetime import datetime, timedelta
from sqlalchemy import or_, func, and_
import pytz
from utils import get_current_utc_time, is_there_this_user
from dotenv import load_dotenv
import os
import security
import string

from schemas.s_auth import UserCreate, ValidateEmailBase, ResendEmailModel, LoginModel, ForgotPasswordModel
from schemas.s_chat import ChatItem

load_dotenv()

istanbul_tz = pytz.timezone('Europe/Istanbul')

app = FastAPI()

EXEMPT_PATHS = [
    "/users/login",
    "/users/register",
    "/users/validate-email",
    "/users/resend-email",
    "/users/refresh",
    "/users/forgot-password"
]

# Middleware ekle
app.add_middleware(AuthMiddleware, exempt_paths=EXEMPT_PATHS)

db = Database()

redis_handler = RedisHandler()

def generate_code(x:bool=True):
    if x == True:
        return ''.join(random.choices('0123456789', k=6))
    else:
        return ''.join(random.choices('0123456789', k=4))

# Kullanım

@app.on_event("startup")
async def on_startup():
    await redis_handler.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await redis_handler.close()



@app.post("/users/register")
async def register(data: UserCreate, background_tasks: BackgroundTasks, session: AsyncSession = Depends(db.get_session)):
    try:
        now = get_current_utc_time()
        print(now)
        query = await session.execute(select(User).where(User.email == data.email))
        current_user = query.scalars().first()
        if current_user:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "User Already Exists"}
            )
        hashed_password = security.hash_password(data.password)
        new_user = User(
            username=data.username,
            password=hashed_password,
            email=data.email
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        validation_code = generate_code()

        await redis_handler.set(key=f"validation_code:{new_user.id}", value=validation_code, expire_seconds=os.getenv("VALIDATION_KEY_EXPIRED_SECOND"))

        background_tasks.add_task(
            send_email_smtp,
            recipient_email="yigitkagankilic98@gmail.com",
            subject="Doğrulama Kodu Maili",
            body=f"Doğrulama kodunu bu şekildedir: {validation_code}",
        )

        new_validation_email_log = ValidationEmailLog(
            user_id=new_user.id,
            is_success=True,
            sent_date=now,
            type="Validation"
        )
        session.add(new_validation_email_log)
        await session.commit()

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message" : "User Created Successfully", "user_id" : new_user.id}
        )
    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message" : "Internal Server Error"}
        )

@app.post("/users/validate-email")
async def validate_email(data: ValidateEmailBase, session: AsyncSession = Depends(db.get_session)):
    try:
        current_user = await is_there_this_user(data.userId, session)
        print(jsonable_encoder(current_user))
        print(data.userId)
        if current_user == None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "User Not Found"}
            )
        
        redis_key = f"validation_code:{current_user.id}"

        validation_code = await redis_handler.get(key=redis_key)
        if validation_code == data.code:
            current_user.is_email_validation = True
            current_user.updated_date = datetime.now(istanbul_tz)
            await session.commit()
            await redis_handler.delete(key=redis_key)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message" : "Başarıyla Doğrulandı", "data" : True}
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Doğrulanamadı", "data" : False}
            )
    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message" : "Internal Server Error"}
        )

@app.post("/users/resend-email")
async def resend_email(data: ResendEmailModel, background_tasks: BackgroundTasks, session: AsyncSession = Depends(db.get_session)):
    try:
        current_user = await is_there_this_user(data.userId, session)
        if current_user == None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message" : "User Not Found"}
            )
        
        current_utc_time = get_current_utc_time()
        two_minutes_ago = current_utc_time - timedelta(minutes=2)
        
        query = await session.execute(
            select(ValidationEmailLog).where(
                ValidationEmailLog.user_id == data.userId,
                ValidationEmailLog.sent_date >= two_minutes_ago,
                ValidationEmailLog.type == "Validation"
            )
        )
        
        log_record = query.scalars().first()
        
        if log_record:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message" : "There is already a code"}
            )
        else:
            validation_code = generate_code()
            redis_key = f"validation_code:{current_user.id}"
            await redis_handler.set(key=redis_key, value=validation_code, expire_seconds=os.getenv("VALIDATION_KEY_EXPIRED_SECOND"))
            background_tasks.add_task(
            send_email_smtp,
            recipient_email=current_user.email,
            subject="Doğrulama Kodu Maili",
            body=f"Doğrulama kodunu bu şekildedir: {validation_code}"
            )

            new_validation_email_log = ValidationEmailLog(
                user_id=current_user.id,
                is_success=True,
                sent_date=current_utc_time,
                type="Validation"
            )
            session.add(new_validation_email_log)
            await session.commit()  
    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message" : "Internal Server Error"}
        )

# @app.post("/users/login")
# async def login_for_access_token(form_data: LoginModel, session: AsyncSession = Depends(db.get_session)): # UserLogin şeması kullanılıyor
#     """
#     Kullanıcı girişi. E-posta ve şifre ile token alınır.
#     """
#     try:
#         # 1. Kullanıcıyı email ile bul
#         query = select(User).where(User.email == form_data.email, User.password == form_data.password)
#         result = await session.execute(query)
#         user = result.scalars().first()

#         # 2. Kullanıcı yoksa veya şifre yanlışsa hata ver
#         # Modeldeki alan adı 'hashed_password' olmalı
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Geçersiz e-posta veya şifre.",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )

#         # 4. Erişim token'ı oluştur
#         # User modelinde uuid ve role_id alanları olduğunu varsayıyoruz
#         access_token_data = {"user_id": user.id}
#         access_token = security.create_access_token(data=access_token_data)
        
#         return JSONResponse(
#             status_code=status.HTTP_200_OK,
#             content={"message" : "Login Successfully", "access_token" : access_token, "token_type" : "bearer", "username" : user.username}
#         )
#     except Exception as e:
#         print(e)
#         return JSONResponse(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             content={"message" : "Internal Server Error"}
#         )

@app.post("/users/login")
async def login_for_access_token(
    form_data: LoginModel, 
    session: AsyncSession = Depends(db.get_session)
):
    """
    Kullanıcı girişi. E-posta ve şifre ile token alınır.
    """
    try:
        # Kullanıcıyı email ile bul
        query = select(User).where(User.email == form_data.email)
        result = await session.execute(query)
        user = result.scalars().first()

        print("here")

        if not user or not security.verify_password(form_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz e-posta veya şifre.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Access & Refresh token oluştur
        token_payload = {"user_id": user.id, "username": user.username}
        access_token = security.create_access_token(data=token_payload)
        refresh_token = security.create_refresh_token(data=token_payload)
        
        print("here")

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Login Successfully",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user.id
            }
        )
    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Internal Server Error"}
        )

@app.post("/users/refresh")
async def refresh_access_token(
    refresh_token: str = Body(..., embed=True),  # Flutter'dan gelen {"refresh_token": "..."}
    session: AsyncSession = Depends(db.get_session)
):
    try:
        decoded = security.validate_token(refresh_token)
        if not decoded:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz veya süresi dolmuş refresh token."
            )

        # Kullanıcı var mı kontrol et
        query = select(User).where(User.id == decoded["user_id"])
        result = await session.execute(query)
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kullanıcı bulunamadı."
            )

        # Yeni access token oluştur
        token_payload = {"user_id": user.id, "username": user.username}
        new_access_token = security.create_access_token(data=token_payload)

        # İsteğe bağlı: yeni refresh token de üret
        new_refresh_token = security.create_refresh_token(data=token_payload)

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,  # İstersen gönderme, ama Flutter kodun bekliyor
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception as e:
        print("Refresh token hatası:", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error"
        )

def generate_password(length=12):
    # Karakter havuzu: harfler, rakamlar ve özel karakterler
    characters = string.ascii_letters + string.digits + string.punctuation
    
    # Rastgele şifre oluştur
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

@app.post("/users/forgot-password")
async def forgot_password(data: ForgotPasswordModel, background_tasks: BackgroundTasks, session: AsyncSession = Depends(db.get_session)):
    try:
        # 1. Kullanıcıyı email ile bul
        query = select(User).where(User.email == data.email)
        result = await session.execute(query)
        user = result.scalars().first()
        current_utc_time = get_current_utc_time()

        # 2. Kullanıcı yoksa veya şifre yanlışsa hata ver
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz e-posta",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        new_password = generate_password() 

        hashed_password = security.hash_password(new_password)

        user.password = hashed_password

        await session.commit()
        await session.refresh(user)

        background_tasks.add_task(
            send_email_smtp,
            recipient_email=data.email,
            subject="Şifre Sıfırlama Emaili",
            body=f"Yeni şifreniz: {new_password}"
            )
        
        new_validation_email_log = ValidationEmailLog(
            user_id=user.id,
            is_success=True,
            sent_date=current_utc_time,
            type="Forgot Password"
        )
        session.add(new_validation_email_log)
        await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={"message" : "New Password Created Successfully"}
        )
    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Internal Server Error"}
        )

@app.get("/chat/chat-users/{user_id}")
async def get_chats(user_id: int, session: AsyncSession = Depends(db.get_session)):
    try:
        current_user = await is_there_this_user(user_id, session)
        if not current_user:
            return JSONResponse(
                status_code=404,
                content={"message" : "User Not Found"}
            )
        
        current_user_id = current_user.id

        latest_message_subquery = select(
            func.max(Message.sent_date).label('max_sent_date'),
            func.least(Message.sender_id, Message.receiver_id).label("user1"),
            func.greatest(Message.sender_id, Message.receiver_id).label("user2")
        ).filter(
            or_(Message.sender_id == current_user_id, Message.receiver_id == current_user_id)
        ).group_by(
            func.least(Message.sender_id, Message.receiver_id),
            func.greatest(Message.sender_id, Message.receiver_id),
        ).subquery()
        
        # Alt sorgu ile en son mesajları ve ilgili kullanıcıları çek
        stmt = select(Message, User).join(
            User,
            or_(
                User.id == Message.sender_id,
                User.id == Message.receiver_id
            )
        ).filter(
            or_(
                Message.sender_id == current_user_id,
                Message.receiver_id == current_user_id
            ),
            Message.sent_date == latest_message_subquery.c.max_sent_date,
            User.id != current_user_id
        )

        result = await session.execute(stmt)
        latest_messages_with_users = result.all()

        chats_list = []
        for message, other_user in latest_messages_with_users:
            # Okunmamış mesaj sayısını asenkron olarak hesapla
            unread_count_stmt = select(func.count()).filter(
                Message.sender_id == other_user.id,
                Message.receiver_id == current_user_id,
                Message.is_read == False
            )
            unread_count_result = await session.execute(unread_count_stmt)
            unread_count = unread_count_result.scalar_one()

            chats_list.append(ChatItem(
                name=other_user.username,
                receiver_id=other_user.id,
                message=message.content,
                time=message.sent_date.strftime('%H:%M'),
                unread=unread_count,
                avatar=f'https://randomuser.me/api/portraits/men/{other_user.id % 10}.jpg',
                current_user_id=other_user.id
            ))

        print(jsonable_encoder(chats_list))

        return chats_list

    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Internal Server Error"}
        )

@app.get("/chat/messages/{user1_id}/{user2_id}")
async def get_messages_between_users(user1_id: int, user2_id: int, session: AsyncSession = Depends(db.get_session)):
    try:
        user_1 = await is_there_this_user(user1_id, session)
        user_2 = await is_there_this_user(user2_id, session)
        if not user_1 or not user_2:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message" : "User not Found"}
            )
        
        stmt = select(Message).where(
            or_(
                and_(Message.sender_id == user_1.id, Message.receiver_id == user2_id),
                and_(Message.sender_id == user2_id, Message.receiver_id == user1_id),
            )
        ).order_by(Message.sent_date)

        result = await session.execute(stmt)
        messages = result.scalars().all()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"messages" : jsonable_encoder(messages)}
        )

    except Exception as e:
        print(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message" : "Internal Server Error"}
        )