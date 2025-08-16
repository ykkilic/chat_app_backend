import asyncio
import pathlib

from websockets.asyncio.server import serve
# import ssl

from database import Database
from models import User, Message
from utils import is_there_this_user
from datetime import datetime
import json
import pytz

istanbul_tz = pytz.timezone('Europe/Istanbul')

# Aktif bağlantıları saklar: {user_id: websocket}
active_connections = {}

# Room'ları saklar: {room_id: {user_ids: set, type: 'direct'/'group'}}
active_rooms = {}

# Kullanıcının hangi room'larda olduğunu takip eder: {user_id: set(room_ids)}
user_rooms = {}

def generate_room_id(user1_id, user2_id=None, room_type="direct"):
    """
    Room ID oluşturur.
    Direct mesaj için: küçük_id_büyük_id formatında
    Grup mesajı için: grup_timestamp formatında
    """
    if room_type == "direct" and user2_id:
        # Direct mesaj için deterministik room ID
        return f"direct_{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
    elif room_type == "group":
        # Grup mesajı için unique ID (timestamp bazlı)
        import time
        return f"group_{int(time.time() * 1000)}"
    
def get_or_create_room(user_ids, room_type="direct"):
    """
    Room'u getirir veya oluşturur.
    """
    if room_type == "direct" and len(user_ids) == 2:
        user_ids = list(user_ids)
        room_id = generate_room_id(user_ids[0], user_ids[1], "direct")
    else:
        # Grup için yeni room oluştur
        room_id = generate_room_id(user_ids[0], room_type="group")
    
    if room_id not in active_rooms:
        active_rooms[room_id] = {
            'user_ids': set(user_ids),
            'type': room_type
        }
    
    return room_id

def add_user_to_room(user_id, room_id):
    """
    Kullanıcıyı room'a ekler.
    """
    if room_id in active_rooms:
        active_rooms[room_id]['user_ids'].add(user_id)
    
    if user_id not in user_rooms:
        user_rooms[user_id] = set()
    user_rooms[user_id].add(room_id)

def remove_user_from_room(user_id, room_id):
    """
    Kullanıcıyı room'dan çıkarır.
    """
    if room_id in active_rooms:
        active_rooms[room_id]['user_ids'].discard(user_id)
        # Room boşsa sil
        if not active_rooms[room_id]['user_ids']:
            del active_rooms[room_id]
    
    if user_id in user_rooms:
        user_rooms[user_id].discard(room_id)
        if not user_rooms[user_id]:
            del user_rooms[user_id]

def get_user_accessible_rooms(user_id):
    """
    Kullanıcının erişebileceği room'ları döndürür.
    """
    return user_rooms.get(user_id, set())

async def register_connection(user_id, websocket):
    """
    Kullanıcının bağlantısını kaydet.
    """
    active_connections[user_id] = websocket
    print(f"Kullanıcı {user_id} bağlandı ve kaydedildi.")
    print(f"Aktif bağlantı sayısı: {len(active_connections)}")

async def unregister_connection(user_id, websocket):
    """
    Kullanıcı bağlantısını kaldır ve tüm room'lardan çıkar.
    """
    if user_id in active_connections:
        del active_connections[user_id]
        print(f"Kullanıcı {user_id} bağlantısı kesildi.")
        print(f"Aktif bağlantı sayısı: {len(active_connections)}")
    
    # Kullanıcıyı tüm room'lardan çıkar
    if user_id in user_rooms:
        rooms_to_leave = user_rooms[user_id].copy()
        for room_id in rooms_to_leave:
            remove_user_from_room(user_id, room_id)

async def send_to_room(room_id, message_data, sender_id=None):
    """
    Room'daki tüm kullanıcılara mesaj gönder (gönderici hariç).
    """
    if room_id not in active_rooms:
        return
    
    room = active_rooms[room_id]
    message_json = json.dumps(message_data)
    
    for user_id in room['user_ids']:
        # Gönderici kendine mesaj göndermesin
        if sender_id and user_id == sender_id:
            continue
            
        if user_id in active_connections:
            try:
                await active_connections[user_id].send(message_json)
                print(f"Mesaj room {room_id}'dan {user_id} kullanıcısına gönderildi.")
            except Exception as e:
                print(f"Kullanıcı {user_id}'ye mesaj gönderilemedi: {e}")

async def save_message_to_db(sender_id, receiver_id, content, session):
    """
    Mesajı veritabanına kaydet.
    Grup mesajları için receiver_id 0 olarak kaydedilir.
    """
    try:
        message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id if receiver_id else 0,  # Grup için 0
            content=content
        )
        session.add(message)
        await session.commit()
        print(f"Mesaj veritabanına kaydedildi: {sender_id} -> {receiver_id}")
    except Exception as e:
        print(f"Mesaj veritabanına kaydedilemedi: {e}")
        await session.rollback()

async def handle_direct_message(user_id, message_data, session):
    """
    Direct mesaj işle.
    """
    receiver_id = message_data.get('receiver_id')
    content = message_data.get('content')
    
    if not receiver_id or not content:
        return {"status": "error", "message": "Alıcı ID veya içerik eksik."}
    
    # Direct room oluştur/getir
    room_id = get_or_create_room([user_id, receiver_id], "direct")
    
    # Her iki kullanıcıyı da room'a ekle
    add_user_to_room(user_id, room_id)
    add_user_to_room(receiver_id, room_id)
    
    # Mesajı room'a gönder
    message_to_send = {
        "type": "direct_message",
        "room_id": room_id,
        "sender_id": user_id,
        "receiver_id": receiver_id,
        "content": content,
        "timestamp": istanbul_tz.localize(datetime.now()).isoformat()
    }
    
    # Veritabanına kaydet
    await save_message_to_db(user_id, receiver_id, content, session)
    
    # Room'daki diğer kullanıcılara gönder
    await send_to_room(room_id, message_to_send, sender_id=user_id)
    
    return {"status": "success", "message": "Mesaj gönderildi.", "room_id": room_id}

async def handle_group_message(user_id, message_data, session):
    """
    Grup mesajı işle.
    """
    room_id = message_data.get('room_id')
    content = message_data.get('content')
    
    if not room_id or not content:
        return {"status": "error", "message": "Room ID veya içerik eksik."}
    
    # Kullanıcının bu room'a erişimi var mı kontrol et
    if room_id not in get_user_accessible_rooms(user_id):
        return {"status": "error", "message": "Bu room'a erişim yetkiniz yok."}
    
    # Mesajı room'a gönder
    message_to_send = {
        "type": "group_message",
        "room_id": room_id,
        "sender_id": user_id,
        "content": content,
        "timestamp": istanbul_tz.localize(datetime.now()).isoformat()
    }
    
    # Grup mesajları için receiver_id = 0 olarak kaydet
    await save_message_to_db(user_id, 0, f"[{room_id}] {content}", session)
    
    # Room'daki diğer kullanıcılara gönder
    await send_to_room(room_id, message_to_send, sender_id=user_id)
    
    return {"status": "success", "message": "Grup mesajı gönderildi.", "room_id": room_id}

async def handle_create_group(user_id, message_data, session):
    """
    Yeni grup oluştur.
    """
    participant_ids = message_data.get('participant_ids', [])
    group_name = message_data.get('group_name', 'Yeni Grup')
    
    if not participant_ids or not isinstance(participant_ids, list):
        return {"status": "error", "message": "Katılımcı listesi gerekli."}
    
    # Grup oluşturucuyu da ekle
    all_participants = list(set([user_id] + participant_ids))
    
    # Yeni grup room'u oluştur
    room_id = get_or_create_room(all_participants, "group")
    
    # Tüm katılımcıları room'a ekle
    for participant_id in all_participants:
        add_user_to_room(participant_id, room_id)
    
    # Grup oluşturuldu mesajı gönder
    create_message = {
        "type": "group_created",
        "room_id": room_id,
        "creator_id": user_id,
        "group_name": group_name,
        "participants": all_participants,
        "timestamp": istanbul_tz.localize(datetime.now()).isoformat()
    }
    
    # Tüm katılımcılara bildir
    await send_to_room(room_id, create_message)
    
    return {"status": "success", "message": "Grup oluşturuldu.", "room_id": room_id}

async def handle_join_room(user_id, message_data, session):
    """
    Mevcut room'a katıl.
    """
    room_id = message_data.get('room_id')
    
    if not room_id or room_id not in active_rooms:
        return {"status": "error", "message": "Geçersiz room ID."}
    
    # Kullanıcıyı room'a ekle
    add_user_to_room(user_id, room_id)
    
    # Katılım mesajı gönder
    join_message = {
        "type": "user_joined",
        "room_id": room_id,
        "user_id": user_id,
        "timestamp": istanbul_tz.localize(datetime.now()).isoformat()
    }
    
    await send_to_room(room_id, join_message, sender_id=user_id)
    
    return {"status": "success", "message": "Room'a katıldınız.", "room_id": room_id}

async def handle_leave_room(user_id, message_data, session):
    """
    Room'dan ayrıl.
    """
    room_id = message_data.get('room_id')
    
    if not room_id:
        return {"status": "error", "message": "Room ID gerekli."}
    
    # Ayrılma mesajı gönder
    leave_message = {
        "type": "user_left",
        "room_id": room_id,
        "user_id": user_id,
        "timestamp": istanbul_tz.localize(datetime.now()).isoformat()
    }
    
    await send_to_room(room_id, leave_message, sender_id=user_id)
    
    # Kullanıcıyı room'dan çıkar
    remove_user_from_room(user_id, room_id)
    
    return {"status": "success", "message": "Room'dan ayrıldınız.", "room_id": room_id}

async def get_user_rooms_list(user_id):
    """
    Kullanıcının room listesini döndür.
    """
    user_room_ids = get_user_accessible_rooms(user_id)
    rooms_info = []
    
    for room_id in user_room_ids:
        if room_id in active_rooms:
            room = active_rooms[room_id]
            rooms_info.append({
                "room_id": room_id,
                "type": room['type'],
                "participant_count": len(room['user_ids']),
                "participants": list(room['user_ids'])
            })
    
    return {"status": "success", "rooms": rooms_info}

async def handler(websocket, db_instance):    
    async for session in db_instance.get_session():
        user_id = None
        try:
            # İlk mesajı al (kullanıcı kimlik doğrulama)
            message = await websocket.recv()
            message_data = json.loads(message)
            
            if not isinstance(message_data, dict) or 'user_id' not in message_data:
                await websocket.send(json.dumps({"status": "error", "message": "Kullanıcı kimliği gerekli."}))
                return
            
            user_id = message_data['user_id']
            current_user = await is_there_this_user(user_id, session)
            
            if not current_user:
                await websocket.send(json.dumps({"status": "error", "message": "Kullanıcı bulunamadı."}))
                return
            
            await register_connection(user_id, websocket)
            
            # Başarılı bağlantı mesajı
            await websocket.send(json.dumps({
                "status": "connected", 
                "user_id": user_id,
                "message": "WebSocket bağlantısı kuruldu."
            }))
            
            # Mesaj döngüsü
            while True:
                message = await websocket.recv()
                
                try:
                    message_data = json.loads(message)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"status": "error", "message": "Geçersiz JSON formatı."}))
                    continue
                
                if not isinstance(message_data, dict) or 'action' not in message_data:
                    await websocket.send(json.dumps({"status": "error", "message": "Action belirtilmesi gerekli."}))
                    continue
                
                action = message_data['action']
                response = {"status": "error", "message": "Bilinmeyen action."}
                
                try:
                    if action == "send_direct_message":
                        response = await handle_direct_message(user_id, message_data, session)
                    
                    elif action == "send_group_message":
                        response = await handle_group_message(user_id, message_data, session)
                    
                    elif action == "create_group":
                        response = await handle_create_group(user_id, message_data, session)
                    
                    elif action == "join_room":
                        response = await handle_join_room(user_id, message_data, session)
                    
                    elif action == "leave_room":
                        response = await handle_leave_room(user_id, message_data, session)
                    
                    elif action == "get_rooms":
                        response = await get_user_rooms_list(user_id)
                    
                    else:
                        response = {"status": "error", "message": f"Desteklenmeyen action: {action}"}
                    
                except Exception as e:
                    print(f"Action işlemi sırasında hata: {e}")
                    response = {"status": "error", "message": "İşlem sırasında hata oluştu."}
                
                # Yanıtı gönder
                await websocket.send(json.dumps(response))
      
        except Exception as e:
            print("[WEBSOCKET ERROR]", e)
        finally:
            # Bağlantı temizliği
            if user_id:
                await unregister_connection(user_id, websocket)
            try:
                await websocket.close()
            except:
                pass

async def disconnect(websocket):
    print("Bağlantı kesiliyor...")
    try:
        await websocket.close()
    except:
        pass
    print("Bağlantı kesildi.")

# ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
# localhost_pem = pathlib.Path(__file__).with_name("localhost.pem")
# ssl_context.load_cert_chain(localhost_pem)

async def main():
    db = Database()
    async with serve(lambda ws: handler(ws, db), "localhost", 8001) as server:
        print("WebSocket sunucusu başlatıldı: wss://localhost:8001")
        print("Desteklenen aksiyonlar:")
        print("- send_direct_message: Direct mesaj gönder")
        print("- send_group_message: Grup mesajı gönder")
        print("- create_group: Yeni grup oluştur")
        print("- join_room: Room'a katıl")
        print("- leave_room: Room'dan ayrıl")
        print("- get_rooms: Kullanıcının room listesini al")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())