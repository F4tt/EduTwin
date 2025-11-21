from __future__ import annotations

import os
from typing import Dict, List, Optional

from services.llm_provider import get_llm_provider
import httpx
from sqlalchemy.orm import Session

from db import models
from services.intent_detection import ScoreUpdateIntent, detect_score_update_intent
from services.intent_detection import detect_profile_update_intent, detect_personalization_intent
from services import memory_manager
from services.vector_store_provider import get_vector_store

LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


async def _call_remote_llm(messages: List[Dict[str, str]], temperature: float = 0.2) -> Optional[str]:
    provider = get_llm_provider()
    resp = await provider.chat(messages=messages, temperature=temperature)
    if not resp:
        return None

    # tolerant extraction: try several known response shapes (OpenAI-style, Google-style, generic)
    def _extract_text(resp: dict) -> Optional[str]:
        # Official Google Generative AI API response format
        # See: https://ai.google.dev/api/rest/v1beta/models/generateContent
        candidates = resp.get("candidates")
        if isinstance(candidates, list) and candidates:
            cand0 = candidates[0]
            if isinstance(cand0, dict):
                content = cand0.get("content")
                if isinstance(content, dict):
                    parts = content.get("parts")
                    if isinstance(parts, list) and parts:
                        part0 = parts[0]
                        if isinstance(part0, dict) and isinstance(part0.get("text"), str):
                            return part0.get("text")

        # OpenAI Chat completion shape
        choices = resp.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                # ChatCompletions
                msg = first.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg.get("content")
                # choices[].text (older completions)
                if isinstance(first.get("text"), str):
                    return first.get("text")

        # Google/Vertex AI style (legacy)
        outputs = resp.get("outputs")
        if isinstance(outputs, list) and outputs:
            out0 = outputs[0]
            # outputs[0].content could be list of dicts
            content = out0.get("content")
            if isinstance(content, list) and content:
                firstc = content[0]
                if isinstance(firstc, dict) and isinstance(firstc.get("text"), str):
                    return firstc.get("text")
            if isinstance(out0.get("text"), str):
                return out0.get("text")

        # Some APIs return predictions or candidates
        preds = resp.get("predictions")
        if isinstance(preds, list) and preds:
            p0 = preds[0]
            if isinstance(p0, dict):
                if isinstance(p0.get("content"), str):
                    return p0.get("content")
                if isinstance(p0.get("text"), str):
                    return p0.get("text")

        # fallback: scan for first reasonable string in nested structure
        def _scan(obj):
            if isinstance(obj, str) and len(obj) > 5:
                return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    res = _scan(v)
                    if res:
                        return res
            if isinstance(obj, list):
                for v in obj:
                    res = _scan(v)
                    if res:
                        return res
            return None

        return _scan(resp)

    return _extract_text(resp)


def _build_context_blocks(user_id: Optional[int], message: str) -> List[Dict[str, object]]:
    vector_store = get_vector_store()
    filters: Dict[str, object] = {}
    if user_id is not None:
        filters["user_id"] = user_id

    results = vector_store.search(message, top_k=5, filters=filters)
    contexts: List[Dict[str, object]] = []
    for item in results:
        contexts.append(
            {
                "title": item.metadata.get("title"),
                "content": item.content,
                "score": item.score,
                "metadata": item.metadata,
            }
        )
    return contexts


def _build_prompt(message: str, contexts: List[Dict[str, object]], user_profile: Optional[Dict[str, object]]) -> List[Dict[str, str]]:
    instructions = (
        "Bạn là trợ lý học tập thông minh của nền tảng EduTwin. "
        "Luôn phản hồi bằng tiếng Việt, ngắn gọn, thân thiện và tập trung vào việc hỗ trợ học tập. "
        "Nếu có dữ liệu điểm số hoặc thông tin cá nhân liên quan, hãy ưu tiên sử dụng để cá nhân hóa câu trả lời. "
        "Nếu cần cập nhật dữ liệu, hãy yêu cầu xác nhận rõ ràng."
    )

    # build context block
    context_texts = []
    for idx, ctx in enumerate(contexts, start=1):
        title = ctx.get("title") or f"Thông tin #{idx}"
        content = ctx.get("content", "")
        context_texts.append(f"{idx}. {title}\n{content}")

    context_block = "\n\n".join(context_texts) if context_texts else ""

    # user profile block
    profile_block = ""
    if user_profile:
        profile_pairs = [f"{key}: {value}" for key, value in user_profile.items() if value]
        if profile_pairs:
            profile_block = "Thông tin người dùng:\n" + "\n".join(profile_pairs)

    system_msg = instructions
    if profile_block:
        system_msg = f"{system_msg}\n\n{profile_block}"

    # return system-level content and a separate system message for RAG contexts (if any)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_msg}]
    if context_block:
        messages.append({"role": "system", "content": f"Dữ liệu liên quan:\n{context_block}"})

    # the calling code will append prior conversation and the current user message
    return messages


def _derive_score_suggestion(
    db: Session,
    user_id: Optional[int],
    intent: Optional[ScoreUpdateIntent],
) -> Optional[Dict[str, object]]:
    if not user_id or not intent:
        return None

    query = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id, models.StudyScore.subject == intent.subject)
    )
    if intent.grade_level:
        query = query.filter(models.StudyScore.grade_level == intent.grade_level)
    if intent.semester:
        query = query.filter(models.StudyScore.semester == intent.semester)

    score_entry = query.order_by(models.StudyScore.updated_at.desc()).first()
    if not score_entry:
        return None

    suggestion = {
        "score_id": score_entry.id,
        "subject": score_entry.subject,
        "grade_level": score_entry.grade_level,
        "semester": score_entry.semester,
        "current_score": score_entry.actual_score,
        "suggested_score": round(intent.new_score, 2),
        "confidence": intent.confidence,
    }

    if intent.old_score is None and score_entry.actual_score is not None:
        suggestion["detected_old_score"] = score_entry.actual_score
    elif intent.old_score is not None:
        suggestion["detected_old_score"] = round(intent.old_score, 2)

    if (
        score_entry.actual_score is not None
        and abs(score_entry.actual_score - suggestion["suggested_score"]) < 1e-6
    ):
        return None

    return suggestion


async def generate_chat_response(
    *,
    db: Session,
    user: Optional[Dict[str, object]],
    message: str,
    session_id: Optional[str],
) -> Dict[str, object]:
    user_id = user.get("user_id") if user else None
    contexts = _build_context_blocks(user_id, message)
    system_messages = _build_prompt(message, contexts, user)

    # If no session_id supplied but we have an authenticated user, create a persisted ChatSession
    # so the very first message is stored and accessible across logins.
    if not session_id and user_id:
        try:
            import logging
            logger = logging.getLogger("uvicorn.error")
            logger.info(f"generate_chat_response: creating session for user_id={user_id}")
            new_session = models.ChatSession(user_id=user_id, title=None)
            db.add(new_session)
            db.commit()
            db.refresh(new_session)
            session_id = str(new_session.id)
            logger.info(f"generate_chat_response: created session id={session_id} for user_id={user_id}")
            # enforce max 20 sessions per user
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
            logging.getLogger("uvicorn.error").exception(f"Error creating session in generate_chat_response: {e}")
            try:
                db.rollback()
            except Exception:
                pass

    # build conversation messages: include prior session history (if available)
    conversation_messages: List[Dict[str, str]] = []
    if session_id:
        sid = None
        try:
            sid = int(session_id)
        except Exception:
            sid = None
        if sid is not None:
            session = db.query(models.ChatSession).filter(models.ChatSession.id == sid).first()
            if session:
                for m in session.messages:
                    role = m.role if m.role in ("user", "assistant", "system") else "user"
                    conversation_messages.append({"role": role, "content": m.content})

    # current user message appended at end
    conversation_messages.append({"role": "user", "content": message})

    # finalize message list: system messages first, then history, then the current user message
    messages = []
    messages.extend(system_messages)
    messages.extend(conversation_messages)

    try:
        answer = await _call_remote_llm(messages) or "Hiện tại chưa có phản hồi từ mô hình. Bạn có thể thử lại sau nhé."
    except Exception as exc:  # noqa: BLE001
        answer = (
            "Xin lỗi, hệ thống không kết nối được với mô hình ngôn ngữ. "
            "Mình sẽ cố gắng hỗ trợ dựa trên dữ liệu có sẵn.\n\n"
            + "\n\n".join(ctx.get("content", "") for ctx in contexts[:2])
        )
        contexts.append({"error": str(exc)})

    intent = detect_score_update_intent(message)
    score_suggestion = _derive_score_suggestion(db, user_id, intent)

    # Detect profile updates
    profile_candidate = detect_profile_update_intent(message)
    pending_profile = None
    if profile_candidate and user_id:
        # create pending update so user can confirm
        # We only try to set a tentative update if the detected candidate has at least moderate confidence
        conf = float(profile_candidate.get("confidence", 0))
        field = profile_candidate.get("field")
        value = profile_candidate.get("value")
        if conf >= 0.6 and field and value:
            # For a full detected value (like email/phone/name) we create a pending update
            # and include it in the response payload for the frontend to ask confirmation
            try:
                # handle name splitting heuristics
                pending_field = field
                pending_value = value
                if field == "first_last":
                    parts = value.split()
                    last = parts[0] if parts else value
                    first = " ".join(parts[1:]) if len(parts) > 1 else ""
                    # store name as separate pending updates is safer; prefer setting both
                    pending_profile = memory_manager.create_pending_update(
                        db,
                        user_id=user_id,
                        update_type="profile",
                        field="last_name",
                        old_value=None,
                        new_value=last,
                    )
                    # also create a pending first name if present (frontend can show both)
                    if first:
                        memory_manager.create_pending_update(
                            db,
                            user_id=user_id,
                            update_type="profile",
                            field="first_name",
                            old_value=None,
                            new_value=first,
                        )
                else:
                    pending_profile = memory_manager.create_pending_update(
                        db,
                        user_id=user_id,
                        update_type="profile",
                        field=("first_name" if field == "first_name" else ("last_name" if field == "last_name" else field)),
                        old_value=None,
                        new_value=value,
                    )
            except Exception:
                pending_profile = None

    # Detect explicit write memory cues: if user asked the assistant to remember something
    wants_memory = any(k in message.lower() for k in ("ghi nhớ", "remember", "save this", "nhớ rằng"))
    memory_doc = None
    if wants_memory and user_id:
        # create a short learning document and upsert immediately (non-sensitive)
        try:
            doc_title = "Ghi nhớ từ cuộc trò chuyện"
            memory_doc = memory_manager.create_pending_update(
                db,
                user_id,
                update_type="document",
                field=doc_title,
                old_value=None,
                new_value=message,
            )
            # auto-apply document-type pending updates (non-sensitive)
            memory_manager.apply_pending_update(db, memory_doc.id, user_id)
            memory_doc = None
        except Exception:
            memory_doc = None

    # Detect non-sensitive personalization intents and auto-apply
    try:
        pers = detect_personalization_intent(message)
        if pers and user_id:
            field = pers.get("field")
            value = pers.get("value")
            conf = float(pers.get("confidence", 0))
            if conf >= 0.6 and field and value is not None:
                # map field to preference keys
                pref_key = field
                try:
                    memory_manager.set_user_preference(db, user_id, pref_key, value)
                    # update active sessions with new summary
                    from utils.session_utils import SessionManager
                    sessions = SessionManager.get_user_sessions(user_id)
                    # re-query user to build summary
                    user_obj = db.query(models.User).filter(models.User.id == user_id).first()
                    summary = memory_manager.build_user_summary(user_obj) if user_obj else None
                    for s in sessions:
                        try:
                            SessionManager.update_session_fields(s["session_id"], {"preferences_summary": summary})
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass

    persisted_session_id: Optional[str] = None
    # Persist chat messages to session history when possible
    try:
        if session_id:
            # support numeric ids or string ids coming from frontend
            sid = None
            try:
                sid = int(session_id)
            except Exception:
                sid = None

            if sid is not None:
                session = db.query(models.ChatSession).filter(models.ChatSession.id == sid).first()
                if session:
                    # optional ownership check
                    if user_id is None or session.user_id == user_id:
                        # If session has no title yet, generate a concise title from the first user message
                        if not getattr(session, "title", None):
                            try:
                                def _generate_session_title(text: str) -> str:
                                    if not text:
                                        return "Phiên trò chuyện"
                                    t = text.strip()
                                    # try to take first sentence
                                    for sep in (".", "?", "!", "\n"):
                                        if sep in t:
                                            t = t.split(sep)[0]
                                            break
                                    t = t.strip()
                                    if len(t) > 60:
                                        t = t[:57].rsplit(" ", 1)[0] + "..."
                                    # fallback generic
                                    return t or "Phiên trò chuyện"

                                session.title = _generate_session_title(message)
                            except Exception:
                                session.title = "Phiên trò chuyện"

                        user_msg = models.ChatMessage(session_id=session.id, role="user", content=message)
                        assistant_msg = models.ChatMessage(session_id=session.id, role="assistant", content=answer)
                        db.add(user_msg)
                        db.add(assistant_msg)
                        try:
                            db.commit()
                            persisted_session_id = str(session.id)
                        except Exception:
                            db.rollback()
    except Exception:
        # avoid failing the whole response if persistence fails
        pass

    return {
        "answer": answer,
        "contexts": contexts,
        "pending_score_update": score_suggestion,
        "pending_profile_update": {"id": pending_profile.id, "field": pending_profile.field, "value": pending_profile.new_value} if pending_profile else None,
        "memory_saved": bool(memory_doc is None and wants_memory and user_id),
        "session_id": persisted_session_id,
    }


