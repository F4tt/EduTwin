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
from services import learning_documents
from services.chatbot_service import generate_chat_response
from services.vector_store_provider import get_vector_store
from utils.session_utils import get_current_user, require_auth
from services import memory_manager
from services.personalization_learner import PersonalizationLearner

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
    document_id: int
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

    # If authenticated user and no session id provided, create a persisted ChatSession
    # so the first message becomes a saved session the user can access later.
    if current_user and not sess_id:
        try:
            import logging
            logger = logging.getLogger("uvicorn.error")
            user_id = current_user.get("user_id")
            logger.info(f"chatbot_endpoint: creating session for user_id={user_id}")
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
                            user.preferences["learned"] = learned
                            
                            from sqlalchemy.orm.attributes import flag_modified
                            flag_modified(user, "preferences")
                            
                            learning_db.commit()
                            logger.info(f"[Background] Saved learned preferences: {learned}")
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
    
    # Create session if needed
    if current_user and not sess_id:
        try:
            user_id = current_user.get("user_id")
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
            
            # Send completion event with full response
            yield f"data: {json.dumps({'type': 'done', 'response': response_payload})}\n\n"
            
        except Exception as e:
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

    vector_store = get_vector_store()
    learning_documents.sync_score_embeddings(db, vector_store, [score])

    prediction_service.update_predictions_for_user(db, score.user_id)
    db.commit()

    return {"message": "Đã cập nhật điểm học tập.", "score_id": score.id, "new_score": new_score}


@router.get("/chatbot/pending-updates")
@require_auth
def list_pending_updates(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    updates = memory_manager.list_pending_updates(db, current_user.get("user_id"))
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
def confirm_pending_update(request: Request, payload: PendingUpdateConfirm, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    pu = memory_manager.apply_pending_update(db, payload.update_id, current_user.get("user_id"))
    if not pu:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu cập nhật.")
    return {"message": "Đã áp dụng cập nhật.", "id": pu.id}


@router.post("/chatbot/cancel-update")
@require_auth
def cancel_update(request: Request, payload: PendingUpdateCancel, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    ok = memory_manager.cancel_pending_update(db, payload.update_id, current_user.get("user_id"))
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu.")
    return {"message": "Đã huỷ yêu cầu cập nhật."}


@router.post("/chatbot/sessions")
@require_auth
def create_chat_session(request: Request, payload: CreateSessionPayload, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    session = models.ChatSession(user_id=current_user.get("user_id"), title=payload.title)
    db.add(session)
    db.commit()
    db.refresh(session)

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
async def comment_on_slide(request: Request, payload: CommentRequest, db: Session = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")

    document = (
        db.query(models.LearningDocument)
        .filter(models.LearningDocument.id == payload.document_id, models.LearningDocument.user_id == current_user.get("user_id"))
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu học tập.")

    prompt = (
        "Bạn là một trợ lý giáo viên. Dựa trên nội dung sau, hãy viết một đoạn nhận xét ngắn (1-3 câu) bằng tiếng Việt, "
        "tập trung vào kết quả học tập của học sinh và gợi ý cải thiện nếu cần:\n\n" + document.content
    )

    result = await generate_chat_response(db=db, user=current_user, message=prompt, session_id=payload.session_id)
    comment = result.get("answer")

    if payload.persist and comment:
        meta = document.metadata_ or {}
        meta["llm_comment"] = {"text": comment, "generated_at": datetime.utcnow().isoformat()}
        document.metadata_ = meta
        db.commit()

    return JSONResponse(content={"comment": comment})


