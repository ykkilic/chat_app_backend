from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import User, ValidationEmailLog
import pytz

async def is_there_this_user(user_id: int, session: AsyncSession):
    try:
        current_user_query = await session.execute(select(User).where(User.id == user_id))
        current_user = current_user_query.scalars().first()
        if not current_user:
            return None
        else:
            print("HERE")
            return current_user
    except Exception as e:
        print(e)
        raise e

def get_current_utc_time():
    """
    Sistemin yerel saat ayarlarından bağımsız olarak, 
    mevcut UTC zamanını döndürür.
    """
    return datetime.utcnow().replace(tzinfo=pytz.utc)

def get_current_istanbul_time():
    """
    Sistemin yerel saat ayarlarından etkilenmeden,
    mevcut UTC zamanını alıp İstanbul saat dilimine dönüştürür.

    Returns:
        datetime: İstanbul zaman dilimindeki mevcut zaman.
    """
    # İstanbul zaman dilimini tanımla
    istanbul_tz = pytz.timezone('Europe/Istanbul')
    
    # Sistemin yerel saat ayarlarından bağımsız olarak UTC zamanını al
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    
    # UTC zamanını İstanbul zaman dilimine dönüştür
    now_in_istanbul = utc_now.astimezone(istanbul_tz)
    
    return now_in_istanbul