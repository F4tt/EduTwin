from fastapi import Request, HTTPException, Depends
from functools import wraps
import uuid
from datetime import datetime, timedelta
import redis
import json
import os
import inspect

# Cấu hình Redis cho session storage
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Khởi tạo Redis client với error handling
try:
    redis_client = redis.from_url(REDIS_URL)
    # Test connection
    redis_client.ping()
except Exception as e:
    print(f"Redis connection error: {e}")
    # Fallback to localhost if Redis service not available
    redis_client = redis.from_url("redis://localhost:6379")

# Thời gian hết hạn session (mặc định 24 giờ)
SESSION_EXPIRE_HOURS = 24

class SessionManager:
    """Quản lý session cho ứng dụng"""
    
    @staticmethod
    def create_session(user_data: dict) -> str:
        """Tạo session mới cho user"""
        session_id = str(uuid.uuid4())
        session_data = {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "email": user_data.get("email"),
            "phone": user_data.get("phone"),
            "address": user_data.get("address"),
            "age": user_data.get("age"),
            "name": user_data.get("name"),
            "role": user_data.get("role"),
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        
        # Lưu session vào Redis
        SessionManager._persist_session(session_id, session_data)
        
        return session_id
    
    @staticmethod
    def get_session(session_id: str) -> dict:
        """Lấy thông tin session"""
        if not session_id:
            return None
            
        session_data = redis_client.get(f"session:{session_id}")
        if session_data:
            return json.loads(session_data)
        return None
    
    @staticmethod
    def update_session_activity(session_id: str):
        """Cập nhật thời gian hoạt động cuối"""
        session_data = SessionManager.get_session(session_id)
        if session_data:
            session_data["last_activity"] = datetime.utcnow().isoformat()
            SessionManager._persist_session(session_id, session_data)
    
    @staticmethod
    def destroy_session(session_id: str):
        """Xóa session (đăng xuất)"""
        redis_client.delete(f"session:{session_id}")
    
    @staticmethod
    def extend_session(session_id: str, hours: int = SESSION_EXPIRE_HOURS):
        """Gia hạn session"""
        session_data = SessionManager.get_session(session_id)
        if session_data:
            redis_client.expire(f"session:{session_id}", hours * 3600)

    @staticmethod
    def update_session_fields(session_id: str, updates: dict):
        session_data = SessionManager.get_session(session_id)
        if session_data:
            session_data.update(updates)
            session_data["last_activity"] = datetime.utcnow().isoformat()
            SessionManager._persist_session(session_id, session_data)
    
    @staticmethod
    def get_user_sessions(user_id: int) -> list:
        """Lấy tất cả session của user"""
        pattern = f"session:*"
        sessions = []
        
        for key in redis_client.scan_iter(match=pattern):
            session_data = json.loads(redis_client.get(key))
            if session_data.get("user_id") == user_id:
                sessions.append({
                    "session_id": key.decode().split(":")[1],
                    "data": session_data
                })
        
        return sessions
    
    @staticmethod
    def destroy_all_user_sessions(user_id: int):
        """Xóa tất cả session của user (đăng xuất tất cả thiết bị)"""
        sessions = SessionManager.get_user_sessions(user_id)
        for session_info in sessions:
            SessionManager.destroy_session(session_info["session_id"])

    @staticmethod
    def _persist_session(session_id: str, session_data: dict):
        redis_client.setex(
            f"session:{session_id}",
            SESSION_EXPIRE_HOURS * 3600,
            json.dumps(session_data)
        )

def require_auth(f):
    """Decorator yêu cầu xác thực session"""
    @wraps(f)
    async def decorated_function(request: Request, *args, **kwargs):
        session_id = request.cookies.get('session_id')
        
        if not session_id:
            raise HTTPException(status_code=401, detail="Chưa đăng nhập")
        
        session_data = SessionManager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=401, detail="Session không hợp lệ")
        
        # Cập nhật thời gian hoạt động
        SessionManager.update_session_activity(session_id)
        
        # Lưu thông tin user vào request state
        request.state.current_user = session_data
        
        # Gọi hàm gốc, truyền lại request. Hỗ trợ cả async/sync
        if inspect.iscoroutinefunction(f):
            return await f(request, *args, **kwargs)
        else:
            return f(request, *args, **kwargs)
    return decorated_function

# Role-based authentication removed - not needed for current functionality

def get_current_user(request: Request):
    """Lấy thông tin user hiện tại"""
    return getattr(request.state, 'current_user', None)
