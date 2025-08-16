from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatItem(BaseModel):
    name: str
    receiver_id: int
    message: str
    time: str
    unread: int
    avatar: str
    current_user_id: int

    class Config:
        orm_mode = True 