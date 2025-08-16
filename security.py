import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List
import passlib
import passlib.context
import bcrypt
import time
from dotenv import load_dotenv
import os

load_dotenv()


# Load environment variables
SECRET_KEY = os.getenv("SECURITY_KEY")
ALGORITHM = os.getenv("ALGORITHM")

access_expires_for_process_details = int(os.getenv("ACCESS_EXPIRES_FOR_PROCESS_DETAILS"))
access_expires = int(os.getenv("ACCESS_EXPIRES"))
refresh_expires = int(os.getenv("REFRESH_EXPIRES", 60*60*24*7))

class TokenData(BaseModel):
    """Token data model"""
    user_id: int = None
    roled : str

def create_refresh_token(data: dict):
    """Create a new refresh token"""
    to_encode = data.copy()
    to_encode.update({"exp": time.time() + refresh_expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token_for_process_details(data: dict):
    """Create a new access token"""
    to_encode = data
    to_encode.update({"exp": time.time() + access_expires_for_process_details})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_access_token(data: dict):
    """Create a new access token"""
    to_encode = data
    to_encode.update({"exp": time.time() + access_expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token_survey(data: dict):
    """Create a new access token"""
    to_encode = data
    to_encode.update({"exp": time.time() + access_expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def verify_password(password: str, hashed_password: str) -> bool:
    """Verify the password using bcrypt library"""
    password_bytes = password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    try:
        t= bcrypt.checkpw(password_bytes, hashed_password_bytes)
        return bcrypt.checkpw(password_bytes, hashed_password_bytes)
    except Exception as e:
        print(e)
        return False


def hash_password(password: str) -> str:
    """Hash the password using bcrypt library"""
    password_bytes = password.encode('utf-8')
    hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed_password.decode()

def validate_token(token: str):
    """Validate token and return the user ID"""
   
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.ExpiredSignatureError:
        print("token has expired")
        return False

    except jwt.InvalidTokenError:
        print("invalid token")
        return False