from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import database
from utils.session_utils import require_auth, get_current_user, SessionManager
from services import memory_manager

router = APIRouter(prefix="/user", tags=["User"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PreferencePayload(BaseModel):
    key: str
    value: Any


@router.get("/preferences")
@require_auth
def list_preferences(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    prefs = memory_manager.list_user_preferences(db, current_user.get("user_id"))
    return {"preferences": prefs}


@router.post("/preferences")
@require_auth
def set_preference(request: Request, payload: PreferencePayload, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    try:
        prefs = memory_manager.set_user_preference(db, current_user.get("user_id"), payload.key, payload.value)
        # update all active sessions for user with small summary
        sessions = SessionManager.get_user_sessions(current_user.get("user_id"))
        # build summary from DB
        user = db.query.__class__
        # re-query proper user
        from db import models as dbmodels
        user_obj = db.query(dbmodels.User).filter(dbmodels.User.id == current_user.get("user_id")).first()
        summary = memory_manager.build_user_summary(user_obj) if user_obj else None
        for s in sessions:
            try:
                SessionManager.update_session_fields(s["session_id"], {"preferences_summary": summary})
            except Exception:
                pass
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"preferences": prefs}


@router.put("/preferences/{key}")
@require_auth
def update_preference(request: Request, key: str, payload: PreferencePayload, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    try:
        prefs = memory_manager.set_user_preference(db, current_user.get("user_id"), key, payload.value)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"preferences": prefs}


@router.delete("/preferences/{key}")
@require_auth
def delete_preference(request: Request, key: str, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    try:
        prefs = memory_manager.delete_user_preference(db, current_user.get("user_id"), key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"preferences": prefs}


@router.get("/learned-personalization")
@require_auth
def get_learned_personalization(request: Request, db: Session = Depends(get_db)):
    """Get automatically learned personalization preferences for display in Settings."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    
    try:
        from services.personalization_learner import get_learned_preferences_display
        learned = get_learned_preferences_display(db, current_user.get("user_id"))
        return {"learned_preferences": learned}
    except Exception as exc:
        return {"learned_preferences": [], "error": str(exc)}
