from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator, constr
from db import models, database
from utils.session_utils import SessionManager, require_auth, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models cho request/response
class UserRegister(BaseModel):
    first_name: str
    last_name: str
    username: constr(min_length=3, max_length=32)
    password: constr(min_length=6, max_length=128)

    @field_validator("first_name", "last_name")
    @classmethod
    def only_letters(cls, v: str) -> str:
        if not v or not all((ch.isalpha() or ch.isspace()) for ch in v):
            raise ValueError("Chỉ cho phép chữ cái và khoảng trắng")
        return v.strip()

    @field_validator("username")
    @classmethod
    def username_ascii(cls, v: str) -> str:
        if not v.isascii() or not all(ch.isalnum() or ch in ("_", "-") for ch in v):
            raise ValueError("Tên đăng nhập chỉ được dùng chữ số và chữ cái tiếng Anh (kèm '_' hoặc '-')")
        return v

    @field_validator("password")
    @classmethod
    def password_ascii(cls, v: str) -> str:
        if not v.isascii():
            raise ValueError("Mật khẩu chỉ được dùng ký tự tiếng Anh")
        return v

class UserLogin(BaseModel):
    username: str
    password: str


class UserProfileUpdate(BaseModel):
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    age: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        trimmed = v.strip()
        return trimmed or None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        trimmed = v.strip()
        return trimmed or None

    @field_validator("address")
    @classmethod
    def normalize_address(cls, v: str | None) -> str | None:
        if v is None:
            return v
        trimmed = v.strip()
        return trimmed or None

    @field_validator("age")
    @classmethod
    def normalize_age(cls, v: str | None) -> str | None:
        if v is None:
            return v
        trimmed = v.strip()
        return trimmed or None

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    # Kiểm tra username đã tồn tại
    existing_user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")

    # Hash password
    hashed_pw = pwd_context.hash(user_data.password)
    new_user = models.User(
        username=user_data.username,
        hashed_password=hashed_pw,
        first_name=user_data.first_name.strip(),
        last_name=user_data.last_name.strip(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Đăng ký thành công"}

@router.post("/login")
def login(user_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    if not user_data.username.isascii() or not user_data.password.isascii():
        raise HTTPException(status_code=400, detail="Tên đăng nhập và mật khẩu chỉ được dùng ký tự tiếng Anh")
    user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if not user or not pwd_context.verify(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")

    # Tạo session thay vì JWT token
    full_name = " ".join([p for p in [getattr(user, 'first_name', ''), getattr(user, 'last_name', '')] if p]).strip()
    user_info = {
        "user_id": user.id,
        "username": user.username,
        "first_name": getattr(user, 'first_name', None),
        "last_name": getattr(user, 'last_name', None),
        "email": getattr(user, 'email', None),
        "phone": getattr(user, 'phone', None),
        "address": getattr(user, 'address', None),
        "age": getattr(user, 'age', None),
        "name": full_name or None,
        "role": getattr(user, 'role', 'user')
    }
    
    session_id = SessionManager.create_session(user_info)
    
    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,  # Bảo mật: JavaScript không thể truy cập
        secure=False,    # Để test local (sẽ là True trong production)
        samesite="lax"  # Bảo vệ CSRF
    )
    
    return {
        "message": "Đăng nhập thành công",
        "user": user_info
    }


@router.post("/profile")
@require_auth
def update_profile(request: Request, payload: UserProfileUpdate, db: Session = Depends(get_db)):
    current = get_current_user(request)
    if not current:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user = db.query(models.User).filter(models.User.id == current.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    for field in ("email", "phone", "address", "age"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)

    db.commit()
    db.refresh(user)

    updated = {
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "age": user.age,
    }

    session_id = request.cookies.get("session_id")
    if session_id:
        SessionManager.update_session_fields(session_id, updated)
    return {"message": "Đã cập nhật thông tin", "profile": updated}

@router.post("/logout")
def logout(request: Request, response: Response):
    """Đăng xuất - xóa session"""
    # Lấy session_id từ cookie
    session_id = request.cookies.get('session_id')
    
    if session_id:
        # Xóa session khỏi Redis
        SessionManager.destroy_session(session_id)
    
    # Xóa cookie
    response.delete_cookie("session_id")
    
    return {"message": "Đăng xuất thành công"}

@router.get("/me")
@require_auth
def get_current_user_info(request: Request):
    """Lấy thông tin user hiện tại"""
    user = get_current_user(request)
    return {
        "user": user,
        "message": "Thông tin user hiện tại"
    }

# Advanced session management endpoints removed - not needed for basic functionality
