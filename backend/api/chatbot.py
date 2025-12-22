from __future__ import annotations

from datetime import datetime
from typing import Optional
import json
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger("uvicorn.error")

from db import database, models
from services.chatbot_service import generate_chat_response, _build_chart_prompt
from utils.session_utils import get_current_user, require_auth
from services.personalization_learner import PersonalizationLearner
from services.proactive_engagement import ProactiveEngagement
from core.websocket_manager import emit_chat_message, emit_chat_typing


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



class CreateSessionPayload(BaseModel):
    title: Optional[str] = None


class UpdateSessionPayload(BaseModel):
    title: Optional[str] = None


from typing import List

class SectionPrompt(BaseModel):
    section: str
    prompt: str

class CommentRequest(BaseModel):
    insight_type: str = 'slide_comment'  # Type of AI insight
    context_key: Optional[str] = None     # Context identifier (e.g., 'overview_chart', 'Math')
    prompt_context: Optional[str] = None  # Additional context for the prompt
    session_id: Optional[int] = None
    persist: bool = False
    chart_data: Optional[dict] = None     # Chart-specific data for optimized prompting
    active_tab: Optional[str] = None      # Active tab in frontend (for optimized generation)
    sections: Optional[List[SectionPrompt]] = None  # List of section+prompt for multi-section insight
    score_data: Optional[dict] = None     # Comprehensive score data from frontend
    document_context: Optional[dict] = None  # Document summaries from structure
    structure_id: Optional[int] = None    # Structure ID for filtering insights by structure


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
            if cookie_sid:
                sess_data = SessionManager.get_session(cookie_sid)
                if sess_data:
                    current_user = sess_data
            # If still not found, and the client included a user id hint, accept it as current_user
            if not current_user and client_user_id:
                try:
                    uid = int(client_user_id)
                    current_user = {"user_id": uid}
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
            
            # If no current session found, create a new one
            if not sess_id:
                new_session = models.ChatSession(user_id=user_id, title=None)
                db.add(new_session)
                db.commit()
                db.refresh(new_session)
                sess_id = str(new_session.id)

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
    # Uses HYBRID approach: keyword detection + LLM analysis
    if current_user and sess_id:
        import asyncio
        
        async def async_hybrid_learning():
            learning_db = database.SessionLocal()
            try:
                session_id_int = int(sess_id)
                session = learning_db.query(models.ChatSession).filter_by(id=session_id_int).first()
                if session:
                    learning_db.refresh(session)
                    msg_count = len(session.messages)
                    
                    # Trigger every 3 messages (more frequent personalization updates)
                    if msg_count % 3 == 0 and msg_count >= 3:
                        logger.info(f"[HYBRID] Starting personalization learning for user {current_user.get('user_id')} after {msg_count} messages")
                        
                        from services.hybrid_personalization_learner import update_user_personalization_hybrid
                        result = await update_user_personalization_hybrid(
                            db=learning_db,
                            user_id=current_user.get("user_id"),
                            session=session
                        )
                        
                        if result.get("updated"):
                            logger.info(f"[HYBRID] Updated preferences: {result.get('categories_updated')}")
                        
            except Exception as e:
                logger.exception(f"Error in hybrid personalization learning: {e}")
                learning_db.rollback()
            finally:
                learning_db.close()
        
        # Run async task in background
        asyncio.create_task(async_hybrid_learning())
    
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
    Generate AI insights for DataViz dashboard.
    For insight_type='slide_comment', generates multiple insights for sections in a single request.
    Returns structure compatible with frontend expectations.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập.")
    user_id = current_user.get("user_id")
    active_tab = payload.active_tab
    context_key = payload.context_key

    # Multi-section insight generation for DataViz
    if payload.insight_type == 'slide_comment' and payload.sections:
        from services.llm_provider import get_llm_provider
        
        # Use score_data from frontend if provided, otherwise fallback to database
        score_summary = {}
        structure_info = {}
        
        if payload.score_data:
            # Use data sent from frontend
            
            # Get structure info
            structure_info = payload.score_data.get('structure', {})
            
            # Build score summary from bySubject data
            by_subject = payload.score_data.get('bySubject', {})
            for subject, scores in by_subject.items():
                for score_item in scores:
                    key = f"{subject}_{score_item.get('timepoint', '')}"
                    score_summary[key] = float(score_item.get('score', 0))
        else:
            # Fallback: query from database
            active_structure = db.query(models.CustomTeachingStructure).filter(
                models.CustomTeachingStructure.is_active == True
            ).first()
            if not active_structure:
                return JSONResponse(content={
                    "slide_comments": {},
                    "comments_version": 3
                })
            user_scores = db.query(models.CustomUserScore).filter(
                models.CustomUserScore.user_id == user_id,
                models.CustomUserScore.structure_id == active_structure.id
            ).all()
            if not user_scores:
                return JSONResponse(content={
                    "slide_comments": {},
                    "comments_version": 3
                })
            for score in user_scores:
                key = f"{score.subject}_{score.time_point}"
                val = score.actual_score if score.actual_score is not None else score.predicted_score
                if val is not None:
                    score_summary[key] = val
        
        # Build document context if provided
        document_summary = ""
        if payload.document_context:
            doc_ctx = payload.document_context
            summaries = doc_ctx.get('summaries', [])
            if summaries:
                doc_parts = []
                for doc in summaries[:3]:  # Limit to 3 documents to avoid token limit
                    doc_parts.append(f"- {doc.get('fileName', 'Tài liệu')}: {doc.get('summary', '')[:500]}")
                document_summary = "\n".join(doc_parts)
        
        # Build comprehensive system prompt - Expert-level analysis style
        system_prompt_parts = [
            """Bạn là CHUYÊN GIA TƯ VẤN GIÁO DỤC với 20 năm kinh nghiệm phân tích dữ liệu học sinh.

⚠️ QUY TẮC ĐỊNH DẠNG BẮT BUỘC:
- TUYỆT ĐỐI KHÔNG sử dụng dấu ** hoặc __ để in đậm (ví dụ: **text** hoặc __text__)
- KHÔNG dùng markdown formatting
- Viết văn bản thuần (plain text) 
- Có thể dùng emoji để nhấn mạnh (💡, ⚠️, 🔴, ✅, 📈, 📉)
- Dùng dấu gạch ngang (-) hoặc số thứ tự (1. 2. 3.) nếu cần liệt kê

NGUYÊN TẮC PHÂN TÍCH:
1. KHÔNG bao giờ chỉ "đọc lại số liệu bằng chữ" (ví dụ: "Điểm Toán kỳ 1 là 7.5, kỳ 2 là 8.0")
2. PHẢI tìm ra PATTERN ẨN, XU HƯỚNG, và ĐIỂM BẤT THƯỜNG mà người thường không nhận ra
3. Phân tích như một chiến lược gia - xác định môn "chiến lược" có thể tạo đột phá
4. Đưa ra NHẬN ĐỊNH SẮC BÉN, KHÁC BIỆT - không chung chung

⚠️ QUAN TRỌNG - CẢNH BÁO SỤT GIẢM:
- Khi phát hiện xu hướng GIẢM điểm, SỤT GIẢM, hay DẤU HIỆU ĐÁNG LO: PHẢI CẢNH BÁO RÕ RÀNG
- Dùng ngôn ngữ mạnh: "cần chú ý ngay", "báo động", "đáng lo ngại", "cần can thiệp"
- Không chỉ "gợi ý cải thiện" mà phải "cảnh tỉnh" về hậu quả nếu không hành động
- Ví dụ: "⚠️ Điểm Toán đang trong đà rơi tự do - giảm 15% chỉ trong 2 kỳ. Nếu không can thiệp ngay, có nguy cơ mất khả năng cạnh tranh ở các tổ hợp khối A, B."

PHONG CÁCH VIẾT:
- Ngắn gọn, súc tích, đi thẳng vào insight
- Dùng ngôn ngữ của chuyên gia nhưng dễ hiểu
- Có thể dùng phép so sánh, ẩn dụ để sinh động
- Kết thúc bằng gợi ý hành động cụ thể khi phù hợp
- Khi có sụt giảm: dùng emoji ⚠️ hoặc 🔴 để nhấn mạnh

VÍ DỤ PHÂN TÍCH TỐT:
❌ SAI: "Điểm Toán tăng từ 7.0 lên 8.0, cho thấy sự tiến bộ."
✅ ĐÚNG: "Toán đang là 'đầu tàu' kéo điểm tổng lên - mức tăng trưởng 14% cho thấy phương pháp học đang hiệu quả."

❌ SAI: "Điểm Lý giảm từ 7.0 xuống 6.0, cần cố gắng hơn."
✅ ĐÚNG: "⚠️ Tín hiệu CẢNH BÁO từ môn Lý - sụt giảm 14% liên tiếp 2 kỳ. Đây là dấu hiệu mất nền tảng, cần ưu tiên khắc phục NGAY trước khi ảnh hưởng đến các tổ hợp khối A, B."

❌ SAI: "Học sinh có điểm Văn cao, điểm Lý thấp."  
✅ ĐÚNG: "Profile rõ ràng thiên Xã hội - sự chênh lệch Văn-Lý tới 2.5 điểm gợi ý nên tập trung khối C, D thay vì ép sức vào A, B."

Hãy phân tích dữ liệu học sinh như một chuyên gia thực thụ - vừa khích lệ khi tốt, vừa cảnh tỉnh khi có vấn đề."""
        ]
        
        if structure_info:
            structure_name = structure_info.get('name', 'Không xác định')
            scale_type = structure_info.get('scaleType', '0-10')
            current_grade = structure_info.get('currentGrade', '')
            subjects = structure_info.get('subjects', [])
            time_points = structure_info.get('timePoints', [])
            
            system_prompt_parts.append(f"\nThông tin cấu trúc học tập:")
            system_prompt_parts.append(f"- Tên cấu trúc: {structure_name}")
            system_prompt_parts.append(f"- Thang điểm: {scale_type}")
            if current_grade:
                system_prompt_parts.append(f"- Mốc thời gian hiện tại: {current_grade}")
            if subjects:
                system_prompt_parts.append(f"- Các môn học: {', '.join(subjects[:10])}")
            if time_points:
                system_prompt_parts.append(f"- Các mốc thời gian: {', '.join(time_points[:6])}")
        
        if document_summary:
            system_prompt_parts.append(f"\nTài liệu tham khảo về cách đánh giá và phân tích:")
            system_prompt_parts.append(document_summary)
        
        system_prompt = "\n".join(system_prompt_parts)
        
        provider = get_llm_provider()
        results = {}
        
        # =============================================================
        # OPTIMIZED: Single LLM call for ALL sections (saves tokens!)
        # =============================================================
        
        # Build a combined prompt with all section requirements
        section_prompts = []
        section_keys = [s.section for s in payload.sections]
        
        for section in payload.sections:
            section_name = section.section
            prompt = section.prompt
            
            # Build section-specific data context
            section_data = {}
            if payload.score_data:
                by_subject = payload.score_data.get('bySubject', {})
                avg_by_timepoint = payload.score_data.get('averageByTimepoint', {})
                
                if section_name in by_subject:
                    section_data[section_name] = by_subject[section_name]
                elif section_name in ['summary', 'trend', 'subjects', 'radar']:
                    section_data['averageByTimepoint'] = avg_by_timepoint
                    subject_avgs = {}
                    for subj, scores in by_subject.items():
                        all_scores = [float(s.get('score', 0)) for s in scores if s.get('score')]
                        if all_scores:
                            subject_avgs[subj] = round(sum(all_scores) / len(all_scores), 2)
                    section_data['subjectAverages'] = subject_avgs
                else:
                    section_data = {k: v for k, v in by_subject.items()}
            
            data_str = json.dumps(section_data, ensure_ascii=False) if section_data else json.dumps(score_summary, ensure_ascii=False)
            section_prompts.append(f'"{section_name}": {prompt} [Dữ liệu: {data_str}]')
        
        # Combined user prompt requesting JSON output
        combined_prompt = f"""Phân tích các phần sau và trả về KẾT QUẢ dưới dạng JSON với các key tương ứng.
Mỗi value là một đoạn phân tích ngắn gọn (2-4 câu).

CÁC PHẦN CẦN PHÂN TÍCH:
{chr(10).join(section_prompts)}

ĐỊNH DẠNG TRẢ VỀ (JSON thuần, không có markdown code block):
{{
  "{section_keys[0]}": "Nội dung phân tích cho {section_keys[0]}...",
  ...
}}

CHÚ Ý: 
- Chỉ trả về JSON object, không có text giải thích trước/sau
- Mỗi phần tích tối đa 3-4 câu, ngắn gọn súc tích
- KHÔNG dùng ** hoặc __ markdown"""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": combined_prompt}
            ]
            
            logger.info(f"[AI_INSIGHTS] Sending SINGLE request for {len(payload.sections)} sections")
            response = await provider.chat(messages=messages, temperature=0.3)
            
            # Parse response
            response_text = ""
            if response and isinstance(response, dict):
                candidates = response.get("candidates", [])
                if candidates and isinstance(candidates[0], dict):
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and isinstance(parts[0], dict):
                        response_text = parts[0].get("text", "")
            
            # Try to parse JSON from response
            parsed_results = {}
            if response_text:
                # Clean up response text (remove markdown code blocks if present)
                clean_text = response_text.strip()
                if clean_text.startswith("```"):
                    # Remove markdown code block
                    lines = clean_text.split("\n")
                    clean_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                
                try:
                    parsed_results = json.loads(clean_text)
                    logger.info(f"[AI_INSIGHTS] Successfully parsed {len(parsed_results)} sections from single response")
                except json.JSONDecodeError as je:
                    logger.warning(f"[AI_INSIGHTS] Failed to parse JSON, trying line-by-line: {je}")
                    # Fallback: try to extract key-value pairs
                    for section_key in section_keys:
                        if section_key in response_text:
                            # Simple extraction - find text after the key
                            parsed_results[section_key] = f"Phân tích cho {section_key}: Vui lòng thử lại."
            
            # Map parsed results to output format
            for section in payload.sections:
                section_name = section.section
                comment = parsed_results.get(section_name, "Chưa có phân tích cho mục này.")
                
                # Clean up the comment (remove any markdown that slipped through)
                if isinstance(comment, str):
                    comment = comment.replace("**", "").replace("__", "")
                
                results[section_name] = {
                    "comment": comment,
                    "narrative": {"comment": comment}
                }
                
                # Persist to database with structure_id
                if payload.persist:
                    context_key_db = f"{payload.active_tab}_{section_name}"
                    # Filter by structure_id if provided
                    query = db.query(models.AIInsight).filter(
                        models.AIInsight.user_id == user_id,
                        models.AIInsight.insight_type == 'slide_comment',
                        models.AIInsight.context_key == context_key_db
                    )
                    if payload.structure_id:
                        query = query.filter(models.AIInsight.structure_id == payload.structure_id)
                    existing = query.first()
                    
                    if existing:
                        existing.content = comment
                        existing.updated_at = datetime.utcnow()
                        if payload.structure_id:
                            existing.structure_id = payload.structure_id
                    else:
                        new_insight = models.AIInsight(
                            user_id=user_id,
                            structure_id=payload.structure_id,  # Save structure_id
                            insight_type='slide_comment',
                            context_key=context_key_db,
                            content=comment,
                            metadata_={"generated_at": datetime.utcnow().isoformat()}
                        )
                        db.add(new_insight)
                        
        except Exception as e:
            logger.error(f"[AI_INSIGHTS] Single-call generation failed: {e}")
            # Fallback: return error for all sections
            for section in payload.sections:
                results[section.section] = {
                    "comment": "Không thể tạo phân tích. Vui lòng thử lại.",
                    "narrative": {"comment": "Không thể tạo phân tích. Vui lòng thử lại."}
                }
        
        db.commit()
        
        # Return results in correct format for each tab
        slide_comments = {}
        if payload.active_tab == 'Chung':
            slide_comments['overview'] = results
        elif payload.active_tab == 'Tổ Hợp':
            slide_comments['exam_blocks'] = {"blocks": results}
        elif payload.active_tab == 'Từng Môn':
            slide_comments['subjects'] = results
        else:
            slide_comments = results
        return JSONResponse(content={"slide_comments": slide_comments, "comments_version": 3})

    # For other insight types (legacy support)
    # Detect if this is a chart-related insight
    is_chart = payload.chart_data is not None or 'chart' in (payload.context_key or '').lower()
    comment = None
    if is_chart and payload.chart_data:
        from services.llm_provider import get_llm_provider
        chart_type = payload.context_key or 'overview'
        messages = _build_chart_prompt(payload.chart_data, chart_type, user_id, db)
        if payload.prompt_context:
            messages.append({"role": "user", "content": payload.prompt_context})
        else:
            messages.append({"role": "user", "content": "Hãy phân tích biểu đồ điểm số này."})
        provider = get_llm_provider()
        response = await provider.chat(messages=messages, temperature=0.3)
        if response and isinstance(response, dict):
            candidates = response.get("candidates", [])
            if candidates and isinstance(candidates[0], dict):
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts and isinstance(parts[0], dict):
                    comment = parts[0].get("text", "")
                else:
                    comment = "Không thể tạo nhận xét."
            else:
                comment = "Không thể tạo nhận xét."
        else:
            comment = "Không thể tạo nhận xét."
    else:
        # Use standard chat prompt for non-chart insights
        if payload.prompt_context:
            prompt = payload.prompt_context
        else:
            prompt = (
                "Bạn là một trợ lý giáo viên. Hãy viết một đoạn nhận xét ngắn (1-3 câu) bằng tiếng Việt, "
                "tập trung vào kết quả học tập của học sinh và gợi ý cải thiện nếu cần."
            )
        result = await generate_chat_response(db=db, user=current_user, message=prompt, session_id=payload.session_id)
        comment = result.get("answer")

    # Persist to database if requested
    if payload.persist and comment:
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
            existing.content = comment
            existing.updated_at = datetime.utcnow()
            existing.metadata_ = {
                **(existing.metadata_ or {}),
                "regenerated_at": datetime.utcnow().isoformat(),
                "session_id": payload.session_id
            }
        else:
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
    structure_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Fetch AI insights for the current user.
    Can filter by insight_type, context_key, and/or structure_id.
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
    if structure_id:
        query = query.filter(models.AIInsight.structure_id == structure_id)
    
    insights = query.order_by(models.AIInsight.updated_at.desc()).all()
    
    return JSONResponse(content={
        "insights": [
            {
                "id": ins.id,
                "insight_type": ins.insight_type,
                "context_key": ins.context_key,
                "content": ins.content,
                "structure_id": ins.structure_id,
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



