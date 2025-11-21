from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from db import models
from services.vector_store_provider import get_vector_store
from services import learning_documents
from ml import prediction_service
from utils.session_utils import SessionManager
import json


def create_pending_update(
    db: Session,
    user_id: int,
    update_type: str,
    field: Optional[str],
    old_value: Optional[str],
    new_value: Optional[str],
    metadata: Optional[Dict] = None,
) -> models.PendingUpdate:
    pu = models.PendingUpdate(
        user_id=user_id,
        update_type=update_type,
        field=field,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        metadata_=metadata or {},
    )
    db.add(pu)
    db.flush()
    return pu


def list_pending_updates(db: Session, user_id: int):
    return db.query(models.PendingUpdate).filter(models.PendingUpdate.user_id == user_id).all()


def list_user_preferences(db: Session, user_id: int) -> Dict:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {}
    return user.preferences or {}


def set_user_preference(db: Session, user_id: int, key: str, value) -> Dict:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    prefs = user.preferences or {}
    prefs[key] = value
    user.preferences = prefs
    db.commit()

    # update session data if user has active sessions
    try:
        # update session fields with summary so frontend sees immediate change
        summary = build_user_summary(user)
        # store compact profile into session store for quick access
        # SessionManager expects a session_id to update specific session; we cannot update all sessions here.
        # Instead, we update a compact `preferences_summary` per-user key in Redis for convenience.
        from utils.session_utils import redis_client
        redis_client.set(f"user:{user_id}:preferences_summary", summary)
    except Exception:
        pass

    # Update vector store for RAG
    try:
        vector_store = get_vector_store()
        profile_text = build_user_summary(user)
        from services.vector_store import VectorItem
        item = VectorItem(vector_id=f"user-{user.id}", content=profile_text, metadata={"user_id": user.id, "type": "user_profile"})
        vector_store.upsert([item])
    except Exception:
        pass

    return user.preferences or {}


def delete_user_preference(db: Session, user_id: int, key: str) -> Dict:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    prefs = user.preferences or {}
    if key in prefs:
        prefs.pop(key, None)
        user.preferences = prefs
        db.commit()
        # update vector
        try:
            vector_store = get_vector_store()
            profile_text = build_user_summary(user)
            from services.vector_store import VectorItem
            item = VectorItem(vector_id=f"user-{user.id}", content=profile_text, metadata={"user_id": user.id, "type": "user_profile"})
            vector_store.upsert([item])
        except Exception:
            pass
    return user.preferences or {}


def build_user_summary(user: models.User) -> str:
    parts = [f"User {user.id} {user.first_name or ''} {user.last_name or ''}".strip()]
    prefs = user.preferences or {}
    # include small set of preferences for RAG
    if prefs.get("salutation"):
        parts.append(f"Salutation: {prefs.get('salutation')}")
    if prefs.get("tone"):
        parts.append(f"Tone: {prefs.get('tone')}")
    if prefs.get("interests"):
        parts.append("Interests: " + ", ".join(prefs.get("interests") if isinstance(prefs.get("interests"), list) else [str(prefs.get("interests"))]))
    if prefs:
        # add a short JSON snippet for other preferences
        try:
            compact = json.dumps({k: v for k, v in prefs.items() if k not in ("interests", "salutation", "tone")}, ensure_ascii=False)
            if compact and compact != "{}":
                parts.append(f"Other: {compact}")
        except Exception:
            pass
    return "\n".join(parts)


def cancel_pending_update(db: Session, update_id: int, user_id: int) -> bool:
    pu = (
        db.query(models.PendingUpdate)
        .filter(models.PendingUpdate.id == update_id, models.PendingUpdate.user_id == user_id)
        .first()
    )
    if not pu:
        return False
    db.delete(pu)
    db.commit()
    return True


def apply_pending_update(db: Session, update_id: int, user_id: int) -> Optional[models.PendingUpdate]:
    """Apply a pending update and return the update applied, or None if not found."""
    pu = (
        db.query(models.PendingUpdate)
        .filter(models.PendingUpdate.id == update_id, models.PendingUpdate.user_id == user_id)
        .first()
    )
    if not pu:
        return None

    # Handle a few types: profile, score, document
    if pu.update_type == "profile":
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None
        # only allow certain fields for safety
        if pu.field in ("first_name", "last_name", "email", "phone"):
            setattr(user, pu.field, pu.new_value)
            db.commit()
            # also update a compact user profile vector for RAG
            try:
                vector_store = get_vector_store()
                parts = [f"User {user.id} {user.first_name or ''} {user.last_name or ''}"]
                if user.email:
                    parts.append(f"Email: {user.email}")
                if user.phone:
                    parts.append(f"Phone: {user.phone}")
                profile_text = "\n".join(parts)
                from services.vector_store import VectorItem

                item = VectorItem(vector_id=f"user-{user.id}", content=profile_text, metadata={"user_id": user.id, "type": "user_profile"})
                vector_store.upsert([item])
            except Exception:
                # ignore vector updates on failure
                pass

    elif pu.update_type == "score":
        # score updates should include a `score_id` in metadata
        score_id = (pu.metadata_ or {}).get("score_id")
        if not score_id:
            return None
        score = db.query(models.StudyScore).filter(models.StudyScore.id == int(score_id)).first()
        if not score:
            return None
        try:
            from datetime import datetime

            score.actual_score = float(pu.new_value)
            score.actual_source = "chat_confirmation"
            score.actual_status = "confirmed"
            score.actual_updated_at = datetime.utcnow()
            db.commit()
            # update embeddings
            vector_store = get_vector_store()
            learning_documents.sync_score_embeddings(db, vector_store, [score])
            prediction_service.update_predictions_for_user(db, score.user_id)
        except Exception:
            db.rollback()
            raise

    elif pu.update_type == "document":
        # Save a learning document created from the chat content
        try:
            from services.vector_store import VectorItem

            user = db.query(models.User).filter(models.User.id == user_id).first()
            document = models.LearningDocument(
                user_id=user_id,
                source="chat_mem",
                reference_type="chat",
                reference_id=None,
                title=pu.field,
                content=pu.new_value or "",
                metadata_={"origin": "chatbot"},
            )
            db.add(document)
            db.flush()
            vector_store = get_vector_store()
            learning_documents.sync_score_embeddings(db, vector_store, [])  # only reusing function
            contents = [document.content]
            embeddings = vector_store.encode(contents)
            items = [VectorItem(vector_id=f"chat-{document.id}", content=document.content, metadata={"user_id": user_id, "document_id": document.id})]
            vector_store.upsert(items, embeddings=embeddings)
            db.commit()
        except Exception:
            db.rollback()
            raise

    # remove pending update after apply
    try:
        db.delete(pu)
        db.commit()
    except Exception:
        db.rollback()

    return pu
