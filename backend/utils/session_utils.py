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

# Khởi tạo Redis client (lazy connection - không test ngay)
redis_client = redis.from_url(
    REDIS_URL,
    socket_connect_timeout=5,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30
)

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
            "current_grade": user_data.get("current_grade"),
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
    def set_first_time_completed(user_id: int):
        """Mark that the user has completed (or skipped) the first-time flow."""
        try:
            redis_client.set(f"user:{user_id}:first_time_completed", "1")
        except Exception:
            pass

    @staticmethod
    def get_first_time_completed(user_id: int) -> bool:
        """Return True if user has completed first-time flow (persisted)."""
        try:
            val = redis_client.get(f"user:{user_id}:first_time_completed")
            return bool(val)
        except Exception:
            return False
    
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
    # Check if function is async
    if inspect.iscoroutinefunction(f):
        @wraps(f)
        async def async_decorated_function(request: Request, *args, **kwargs):
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
            
            return await f(request, *args, **kwargs)
        return async_decorated_function
    else:
        @wraps(f)
        def sync_decorated_function(request: Request, *args, **kwargs):
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
            
            return f(request, *args, **kwargs)
        return sync_decorated_function

# Role-based authentication removed - not needed for current functionality

def get_current_user(request: Request):
    """Lấy thông tin user hiện tại, raise 401 nếu chưa đăng nhập"""
    session_id = request.cookies.get('session_id')
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    session_data = SessionManager.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session không hợp lệ hoặc đã hết hạn")
    
    # Cập nhật thời gian hoạt động
    SessionManager.update_session_activity(session_id)
    
    # Tạo object giả User để có thể access .id, .username, etc.
    class UserSession:
        def __init__(self, data):
            self._data = data
            self.id = data.get("user_id")
            self.username = data.get("username")
            self.email = data.get("email")
            self.first_name = data.get("first_name")
            self.last_name = data.get("last_name")
            self.phone = data.get("phone")
            self.address = data.get("address")
            self.age = data.get("age")
            self.current_grade = data.get("current_grade")
            self.role = data.get("role")
        
        def get(self, key, default=None):
            """Support dict-like get() method for backward compatibility"""
            return self._data.get(key, default)
    
    return UserSession(session_data)
