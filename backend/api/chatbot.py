from __future__ import annotations

from datetime import datetime
from typing import Optional
import json
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import database, models
from ml import prediction_service
from services.chatbot_service import generate_chat_response
from utils.session_utils import get_current_user, require_auth
from services.personalization_learner import PersonalizationLearner
from services.proactive_engagement import ProactiveEngagement
from core.websocket_manager import emit_chat_message, emit_chat_typing


# Helper functions for pending updates (moved from deleted memory_manager service)
def list_pending_updates_for_user(db: Session, user_id: int):
    return db.query(models.PendingUpdate).filter(models.PendingUpdate.user_id == user_id).all()


def apply_pending_update(db: Session, update_id: int, user_id: int):
    """Apply a pending update and remove it from queue."""
    pu = db.query(models.PendingUpdate).filter(
        models.PendingUpdate.id == update_id,
        models.PendingUpdate.user_id == user_id
    ).first()
    if not pu:
        return None
    
    # Handle profile updates
    if pu.update_type == "profile":
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user and pu.field in ("first_name", "last_name", "email", "phone"):
            setattr(user, pu.field, pu.new_value)
            db.commit()
    
    # Handle score updates
    elif pu.update_type == "score":
        score_id = (pu.metadata_ or {}).get("score_id")
        if score_id:
            score = db.query(models.StudyScore).filter(models.StudyScore.id == int(score_id)).first()
            if score:
                score.actual_score = float(pu.new_value)
                score.actual_source = "chat_confirmation"
                score.actual_status = "confirmed"
                score.actual_updated_at = datetime.utcnow()
                db.commit()
                # REMOVED: vector store sync (no longer used)
                prediction_service.update_predictions_for_user(db, score.user_id)
    
    # Remove pending update after applying
    try:
        db.delete(pu)
        db.commit()
    except Exception:
        db.rollback()
    
    return pu


def cancel_pending_update(db: Session, update_id: int, user_id: int) -> bool:
    """Cancel a pending update without applying it."""
    pu = db.query(models.PendingUpdate).filter(
        models.PendingUpdate.id == update_id,
        models.PendingUpdate.user_id == user_id
    ).first()
    if not pu:
        return False
    try:
        db.delete(pu)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


router = APIRouter(tags=["Chatbot"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(default=None)
    message: str


class ScoreUpdateConfirmation(BaseModel):
    score_id: int
    new_score: float = Field(ge=0, le=10)


class PendingUpdateConfirm(BaseModel):
    update_id: int


class PendingUpdateCancel(BaseModel):
    update_id: int


class CreateSessionPayload(BaseModel):
    title: Optional[str] = None


class UpdateSessionPayload(BaseModel):
    title: Optional[str] = None


class CommentRequest(BaseModel):
    insight_type: str = 'slide_comment'  # Type of AI insight
    context_key: Optional[str] = None     # Context identifier (e.g., 'overview_chart', 'Math')
    prompt_context: Optional[str] = None  # Additional context for the prompt
    session_id: Optional[int] = None
    persist: bool = False


@router.post("/chatbot")
async def chatbot_endpoint(
    request: Request,
    payload: Optional[dict] = Body(None),
    message: Optional[str] = None,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Accept chat input from JSON, form-data, query param `message`, or raw text body.

    Priority: JSON payload -> query param -> form field -> raw text body.
    For unauthenticated requests, current_user will be None and RAG/session features disabled.
    """
    current_user = get_current_user(request)

    msg_text: Optional[str] = None
    sess_id: Optional[str] = None

    if payload:
        # payload may be a plain dict (avoid using Pydantic model in signature
        # to prevent forward-ref issues). Try to parse into ChatRequest, but
        # fall back to extracting common fields.
        try:
            parsed = ChatRequest.model_validate(payload)
            msg_text = (parsed.message or "").strip()
            sess_id = parsed.session_id
        except Exception:
            msg_text = str(payload.get("message") or payload.get("text") or "").strip()
            sess_id = payload.get("session_id")
        # optional client-provided user id hint (used when cookies are not available)
        client_user_id = payload.get("client_user_id") if isinstance(payload, dict) else None

    # Query params override if provided
    if not msg_text and message:
        msg_text = message.strip()
    if not sess_id and session_id:
        sess_id = session_id

    # Try form data
    if not msg_text or not sess_id:
        try:
            form = await request.form()
            if not msg_text:
                fmsg = form.get("message") or form.get("text")
                if fmsg:
                    msg_text = str(fmsg).strip()
            if not sess_id:
                fsess = form.get("session_id")
                if fsess:
                    sess_id = str(fsess)
        except Exception:
            pass

    # Try raw body (text/plain)
    if not msg_text:
        try:
            raw = (await request.body()) or b""
            if raw:
                raw_text = raw.decode(errors="ignore").strip()
                if raw_text:
                    msg_text = raw_text
        except Exception:
            pass

    if not msg_text:
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống.")
    # If no current_user set by decorator, try to obtain from session cookie (frontend sets `session_id` cookie)
    if not current_user:
        try:
            import logging
            logger = logging.getLogger("uvicorn.error")
            from utils.session_utils import SessionManager

            cookie_sid = request.cookies.get("session_id")
            logger.info(f"chatbot_endpoint: cookie_sid={cookie_sid} sess_id_before={sess_id}")
            if cookie_sid:
                sess_data = SessionManager.get_session(cookie_sid)
                logger.info(f"chatbot_endpoint: SessionManager.get_session returned: {bool(sess_data)}")
                if sess_data:
                    current_user = sess_data
            # If still not found, and the client included a user id hint, accept it as current_user
            if not current_user and client_user_id:
                try:
                    uid = int(client_user_id)
                    current_user = {"user_id": uid}
                    logger.info(f"chatbot_endpoint: using client_user_id hint={uid}")
                except Exception:
                    pass
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").exception(f"Error reading session cookie: {e}")
            current_user = None

    # If authenticated user and no session id provided, use the current chat session from login
    # or create a new one if needed
    if current_user and not sess_id:
        try:
            import logging
            logger = logging.getLogger("uvicorn.error")
            user_id = current_user.get("user_id")
            
            # Try to get current_chat_session_id from session (set during login)
            current_chat_session_id = current_user.get("current_chat_session_id")
            if current_chat_session_id:
                # Verify this session still exists and belongs to user
                existing_session = db.query(models.ChatSession).filter(
                    models.ChatSession.id == current_chat_session_id,
                    models.ChatSession.user_id == user_id
                ).first()
                if existing_session:
                    sess_id = str(existing_session.id)
                    logger.info(f"chatbot_endpoint: using current chat session id={sess_id} for user_id={user_id}")
            
            # If no current session found, create a new one
            if not sess_id:
                logger.info(f"chatbot_endpoint: creating new session for user_id={user_id}")
                new_session = models.ChatSession(user_id=user_id, title=None)
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                sess_id = str(new_session.id)
                logger.info(f"chatbot_endpoint: created session id={sess_id} for user_id={user_id}")

                # Enforce maximum persisted sessions per user (keep newest 20)
                try:
                    max_sessions = 20
                    user_sessions = (
                        db.query(models.ChatSession)
                        .filter(models.ChatSession.user_id == user_id)
                        .order_by(models.ChatSession.created_at.desc())
                        .all()
                    )
                    if len(user_sessions) > max_sessions:
                        to_delete = user_sessions[max_sessions:]
                        for s in to_delete:
                            db.delete(s)
                        db.commit()
                except Exception:
                    db.rollback()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").exception(f"Error creating session in chatbot_endpoint: {e}")
            db.rollback()

    response_payload = await generate_chat_response(
        db=db,
        user=current_user,
        message=msg_text,
        session_id=sess_id,
    )
    
    # Emit message via WebSocket to chat session room
    if sess_id:
        try:
            await emit_chat_message(sess_id, {
                'session_id': sess_id,
                'message': response_payload.get('answer'),
                'role': 'assistant',
                'timestamp': datetime.utcnow().isoformat()
            })
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").warning(f"Failed to emit WebSocket message: {e}")
    
    # Auto-learn personalization AFTER response (non-blocking)
    # Run in background to not slow down response
    if current_user and sess_id:
        import threading
        def background_learning():
            learning_db = database.SessionLocal()
            try:
                session_id_int = int(sess_id)
                session = learning_db.query(models.ChatSession).filter_by(id=session_id_int).first()
                if session:
                    learning_db.refresh(session)
                    msg_count = len(session.messages)
                    
                    if msg_count % 5 == 0 and msg_count >= 5:
                        import logging
                        logger = logging.getLogger("uvicorn.error")
                        logger.info(f"[Background] Auto-learning personalization for user {current_user.get('user_id')} after {msg_count} messages")
                        
                        learner = PersonalizationLearner()
                        learned = learner.analyze_session_preferences(session)
                        
                        user = learning_db.query(models.User).filter_by(id=current_user.get("user_id")).first()
                        if user:
                            if not user.preferences:
                                user.preferences = {}
                            
                            # Merge with existing preferences (dict format)
                            existing = user.preferences.get("learned", {})
                            if isinstance(existing, dict):
                                # Merge categories
                                for category, items in learned.items():
                                    if category not in existing:
                                        existing[category] = []
                                    # Add new items, avoid duplicates
                                    for item in items:
                                        if item not in existing[category]:
                                            existing[category].append(item)
                                    # Keep max 5 per category
                                    existing[category] = existing[category][:5]
                                user.preferences["learned"] = existing
                            else:
                                # First time or old format - use new dict
                                user.preferences["learned"] = learned
                            
                            from sqlalchemy.orm.attributes import flag_modified
                            flag_modified(user, "preferences")
                            
                            learning_db.commit()
                            logger.info(f"[Background] Saved learned preferences: {user.preferences['learned']}")
            except Exception as e:
                import logging
                logging.getLogger("uvicorn.error").exception(f"Error in background auto-learning: {e}")
                learning_db.rollback()
            finally:
                learning_db.close()
        
        # Start background thread (non-blocking)
        thread = threading.Thread(target=background_learning, daemon=True)
        thread.start()
    
    return JSONResponse(content=response_payload)


@router.post("/chatbot/stream")
async def chatbot_stream_endpoint(
    request: Request,
    payload: Optional[dict] = Body(None),
    db: Session = Depends(get_db),
):
    """
    Streaming version of chatbot endpoint.
    Returns Server-Sent Events (SSE) for real-time token streaming.
    """
    current_user = get_current_user(request)
    
    # Extract message from payload
    msg_text: Optional[str] = None
    sess_id: Optional[str] = None
    
    if payload:
        try:
            parsed = ChatRequest.model_validate(payload)
            msg_text = (parsed.message or "").strip()
            sess_id = parsed.session_id
        except Exception:
            msg_text = str(payload.get("message") or "").strip()
            sess_id = payload.get("session_id")
    
    if not msg_text:
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống.")
    
    # Create session if needed - use current chat session from login or create new
    if current_user and not sess_id:
        try:
            user_id = current_user.get("user_id")
            
            # Try to get current_chat_session_id from session (set during login)
            current_chat_session_id = current_user.get("current_chat_session_id")
            if current_chat_session_id:
                # Verify this session still exists and belongs to user
                existing_session = db.query(models.ChatSession).filter(
                    models.ChatSession.id == current_chat_session_id,
                    models.ChatSession.user_id == user_id
                ).first()
                if existing_session:
                    sess_id = str(existing_session.id)
            
            # If no current session found, create a new one
            if not sess_id:
                new_session = models.ChatSession(user_id=user_id, title=None)
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                sess_id = str(new_session.id)
        except Exception:
            db.rollback()
    
    async def event_generator():
        """Generate SSE events with streaming tokens"""
        try:
            # Send initial event
            yield f"data: {json.dumps({'type': 'start', 'message': 'Đang xử lý...'})}\n\n"
            
            # Emit typing indicator via WebSocket
            if sess_id:
                try:
                    await emit_chat_typing(sess_id, True)
                except Exception:
                    pass
            
            # Get full response (in production, integrate with streaming LLM)
            response_payload = await generate_chat_response(
                db=db,
                user=current_user,
                message=msg_text,
                session_id=sess_id,
            )
            
            # Stream response word by word
            answer = response_payload.get("answer", "")
            words = answer.split()
            
            for i, word in enumerate(words):
                # Send word chunk
                yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                await asyncio.sleep(0.03)  # 30ms delay for smooth streaming
            
            # Stop typing indicator
            if sess_id:
                try:
                    await emit_chat_typing(sess_id, False)
                except Exception:
                    pass
            
            # Send completion event with full response
            yield f"data: {json.dumps({'type': 'done', 'response': response_payload})}\n\n"
            
            # Emit complete message via WebSocket
            if sess_id:
                try:
                    await emit_chat_message(sess_id, {
                        'session_id': sess_id,
                        'message': answer,
                        'role': 'assistant',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass
            
        except Exception as e:
            # Stop typing on error
            if sess_id:
                try:
                    await emit_chat_typing(sess_id, False)
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/chatbot/confirm-score-update")
@require_auth
def confirm_score_update(
    request: Request,
    payload: ScoreUpdateConfirmation,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    score = (
        db.query(models.StudyScore)
        .filter(
            models.StudyScore.id == payload.score_id,
            models.StudyScore.user_id == current_user.get("user_id"),
        )
        .first()
    )
    if not score:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi điểm phù hợp.")

    new_score = round(float(payload.new_score), 2)
    score.actual_score = new_score
    score.actual_source = "chat_confirmation"
    score.actual_status = "confirmed"
    score.actual_updated_at = datetime.utcnow()

    # REMOVED: vector_store embeddings sync (no longer used)

    prediction_service.update_predictions_for_user(db, score.user_id)
    db.commit()

    return {"message": "Đã cập nhật điểm học tập.", "score_id": score.id, "new_score": new_score}


@router.get("/chatbot/pending-updates")
@require_auth
def list_pending_updates(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    updates = list_pending_updates_for_user(db, current_user.get("user_id"))
    return [
        {
            "id": u.id,
            "type": u.update_type,
            "field": u.field,
            "old_value": u.old_value,
            "new_value": u.new_value,
            "metadata": u.metadata_,
            "created_at": u.created_at,
        }
        for u in updates
    ]
@router.post("/chatbot/confirm-update")
@require_auth
async def confirm_pending_update(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    update_id = payload.get("update_id")
    if not update_id:
        raise HTTPException(status_code=400, detail="Thiếu update_id")
    
    pu = apply_pending_update(db, update_id, current_user.get("user_id"))
    if not pu:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu cập nhật.")
    return {"message": "Đã áp dụng cập nhật.", "id": pu.id}


@router.post("/chatbot/cancel-update")
@require_auth
async def cancel_update(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    update_id = payload.get("update_id")
    if not update_id:
        raise HTTPException(status_code=400, detail="Thiếu update_id")
    
    ok = cancel_pending_update(db, update_id, current_user.get("user_id"))
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu.")
    return {"message": "Đã huỷ yêu cầu cập nhật."}


@router.post("/chatbot/sessions")
@require_auth
def create_chat_session(request: Request, payload: dict = Body(default={}), db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    title = payload.get("title") if payload else None
    session = models.ChatSession(user_id=current_user.get("user_id"), title=title)
    db.add(session)
    db.commit()
    db.refresh(session)

    # Generate initial proactive greeting for new session
    try:
        engagement = ProactiveEngagement(db)
        greeting = engagement.generate_greeting(user_id=current_user.get("user_id"))
        
        # Save greeting as assistant message
        greeting_msg = models.ChatMessage(
            session_id=session.id,
            role="assistant",
            content=greeting
        )
        db.add(greeting_msg)
        db.commit()
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").error(f"Failed to generate initial greeting: {e}")
        db.rollback()

    # Enforce maximum persisted sessions per user (keep newest 20)
    try:
        max_sessions = 20
        user_sessions = (
            db.query(models.ChatSession)
            .filter(models.ChatSession.user_id == current_user.get("user_id"))
            .order_by(models.ChatSession.created_at.desc())
            .all()
        )
        if len(user_sessions) > max_sessions:
            # delete oldest sessions beyond the cap
            to_delete = user_sessions[max_sessions:]
            for s in to_delete:
                db.delete(s)
            db.commit()
    except Exception:
        db.rollback()

    return {"id": session.id, "title": session.title}


@router.get("/chatbot/sessions")
@require_auth
def list_chat_sessions(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    sessions = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == current_user.get("user_id"))
        .order_by(models.ChatSession.updated_at.desc())
        .all()
    )
    return [{"id": s.id, "title": s.title, "created_at": s.created_at, "updated_at": s.updated_at} for s in sessions]


@router.put("/chatbot/sessions/{session_id}")
@require_auth
def update_chat_session(request: Request, session_id: str, payload: UpdateSessionPayload = Body(...), db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    try:
        session_id_int = int(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID phiên không hợp lệ.")

    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id_int, models.ChatSession.user_id == current_user.get("user_id"))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy session.")
    if payload.title is not None:
        session.title = payload.title
    db.commit()
    return {"id": session.id, "title": session.title}


@router.delete("/chatbot/sessions/{session_id}")
@require_auth
def delete_chat_session(request: Request, session_id: str, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    try:
        session_id_int = int(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID phiên không hợp lệ.")

    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id_int, models.ChatSession.user_id == current_user.get("user_id"))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy session.")
    db.delete(session)
    db.commit()
    return {"message": "Đã xóa session."}


@router.delete("/chatbot/cleanup-empty-sessions")
@require_auth
def cleanup_empty_sessions(request: Request, db: Session = Depends(get_db)):
    """Xóa các session không có tin nhắn từ user (chỉ có greeting hoặc rỗng)"""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    
    user_id = current_user.get("user_id")
    
    # Get all sessions for user
    sessions = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == user_id)
        .all()
    )
    
    deleted_count = 0
    for session in sessions:
        # Check if session has any user messages
        has_user_message = any(msg.role == "user" for msg in session.messages)
        
        if not has_user_message:
            db.delete(session)
            deleted_count += 1
    
    db.commit()
    return {"message": f"Đã xóa {deleted_count} phiên trống.", "deleted_count": deleted_count}


@router.get("/chatbot/sessions/{session_id}/messages")
@require_auth
def get_session_messages(request: Request, session_id: str, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    try:
        session_id_int = int(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID phiên không hợp lệ.")

    session = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.id == session_id_int, models.ChatSession.user_id == current_user.get("user_id"))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy session.")
    messages = [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at} for m in session.messages
    ]
    return {"id": session.id, "title": session.title, "messages": messages}


@router.post("/chatbot/comment")
@require_auth
async def generate_ai_insight(request: Request, payload: CommentRequest, db: Session = Depends(get_db)):
    """
    Generate AI insight/comment for various contexts (slide, subject analysis, etc.)
    Can optionally persist the result to database for cross-device sync.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    user_id = current_user.get("user_id")

    # Build prompt based on context
    if payload.prompt_context:
        prompt = payload.prompt_context
    else:
        prompt = (
            "Bạn là một trợ lý giáo viên. Hãy viết một đoạn nhận xét ngắn (1-3 câu) bằng tiếng Việt, "
            "tập trung vào kết quả học tập của học sinh và gợi ý cải thiện nếu cần."
        )

    # Generate AI response
    result = await generate_chat_response(db=db, user=current_user, message=prompt, session_id=payload.session_id)
    comment = result.get("answer")

    # Persist to database if requested
    if payload.persist and comment:
        # Check if insight already exists for this context
        existing = (
            db.query(models.AIInsight)
            .filter(
                models.AIInsight.user_id == user_id,
                models.AIInsight.insight_type == payload.insight_type,
                models.AIInsight.context_key == payload.context_key
            )
            .first()
        )

        if existing:
            # Update existing insight
            existing.content = comment
            existing.updated_at = datetime.utcnow()
            existing.metadata_ = {
                **(existing.metadata_ or {}),
                "regenerated_at": datetime.utcnow().isoformat(),
                "session_id": payload.session_id
            }
        else:
            # Create new insight
            new_insight = models.AIInsight(
                user_id=user_id,
                insight_type=payload.insight_type,
                context_key=payload.context_key,
                content=comment,
                metadata_={
                    "generated_at": datetime.utcnow().isoformat(),
                    "session_id": payload.session_id
                }
            )
            db.add(new_insight)
        
        db.commit()

    return JSONResponse(content={"comment": comment})


@router.get("/chatbot/insights")
@require_auth
async def get_user_insights(
    request: Request, 
    insight_type: Optional[str] = None,
    context_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Fetch AI insights for the current user.
    Can filter by insight_type and/or context_key.
    Returns insights sorted by most recent first.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    user_id = current_user.get("user_id")
    
    query = db.query(models.AIInsight).filter(models.AIInsight.user_id == user_id)
    
    if insight_type:
        query = query.filter(models.AIInsight.insight_type == insight_type)
    if context_key:
        query = query.filter(models.AIInsight.context_key == context_key)
    
    insights = query.order_by(models.AIInsight.updated_at.desc()).all()
    
    return JSONResponse(content={
        "insights": [
            {
                "id": ins.id,
                "insight_type": ins.insight_type,
                "context_key": ins.context_key,
                "content": ins.content,
                "metadata": ins.metadata_,
                "created_at": ins.created_at.isoformat() if ins.created_at else None,
                "updated_at": ins.updated_at.isoformat() if ins.updated_at else None
            }
            for ins in insights
        ]
    })


@router.delete("/chatbot/insights/{insight_id}")
@require_auth
async def delete_insight(request: Request, insight_id: int, db: Session = Depends(get_db)):
    """Delete a specific AI insight."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    user_id = current_user.get("user_id")
    
    insight = (
        db.query(models.AIInsight)
        .filter(models.AIInsight.id == insight_id, models.AIInsight.user_id == user_id)
        .first()
    )
    
    if not insight:
        raise HTTPException(status_code=404, detail="Không tìm thấy insight.")
    
    db.delete(insight)
    db.commit()
    
    return JSONResponse(content={"message": "Đã xóa insight thành công"})



