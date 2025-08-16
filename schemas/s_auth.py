from pydantic import BaseModel

# 3. Pydantic ile istek ve yanıt modellerini tanımlayın
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        orm_mode = True

class ValidateEmailBase(BaseModel):
    userId: int
    code: str

class ResendEmailModel(BaseModel):
    userId: int

class LoginModel(BaseModel):
    email: str
    password: str

class ForgotPasswordModel(BaseModel):
    email: str
