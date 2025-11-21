from __future__ import annotations

import threading
import time
from datetime import datetime, timezone, timedelta
from typing import List

from sqlalchemy.orm import Session

from db import models, database
from services.vector_store_provider import get_vector_store

# Simple pruning/summarization service

DEFAULT_KEEP_N = 50
PRUNE_INTERVAL_SECONDS = int(__import__('os').environ.get('PRUNE_INTERVAL_SECONDS', str(24 * 3600)))


def _score_document(doc: models.LearningDocument) -> float:
    # score by recency and manual priority in metadata
    now = datetime.now(timezone.utc)
    try:
        created = doc.created_at if doc.created_at is not None else now
    except Exception:
        created = now
    age_seconds = max(0.0, (now - created).total_seconds())
    recency_score = 1.0 / (1.0 + age_seconds / (24 * 3600))  # decays daily
    meta = doc.metadata_ or {}
    priority = float(meta.get("priority", 0.5))
    # naive redundancy penalty not computed here
    return 0.6 * recency_score + 0.4 * priority


def prune_user_memory(db: Session, vector_store, user_id: int, keep_n: int = DEFAULT_KEEP_N) -> None:
    docs: List[models.LearningDocument] = (
        db.query(models.LearningDocument)
        .filter(models.LearningDocument.user_id == user_id)
        .all()
    )
    if not docs:
        return

    scored = [(doc, _score_document(doc)) for doc in docs]
    scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)
    keep = scored_sorted[:keep_n]
    to_delete = scored_sorted[keep_n:]

    vector_ids = []
    for doc, _ in to_delete:
        for emb in doc.embeddings:
            if emb.vector_id:
                vector_ids.append(emb.vector_id)
        try:
            db.delete(doc)
        except Exception:
            pass

    db.commit()
    if vector_ids:
        try:
            vector_store.delete(vector_ids)
        except Exception:
            pass


def summarize_user_memory(db: Session, vector_store, user_id: int, max_docs: int = 10) -> None:
    # naive summarizer: take oldest low-priority docs and compress into a single summary document
    docs: List[models.LearningDocument] = (
        db.query(models.LearningDocument)
        .filter(models.LearningDocument.user_id == user_id)
        .order_by(models.LearningDocument.created_at.asc())
        .all()
    )
    if not docs:
        return

    # pick low-priority candidates
    candidates = [d for d in docs if (d.metadata_ or {}).get("priority", 0.5) < 0.6]
    if not candidates:
        return

    take = candidates[:max_docs]
    combined = "\n\n".join(d.content for d in take)
    if not combined:
        return

    # Produce a short summary (naive truncation) — in production call LLM to summarize
    summary = combined[:2000]  # naive cut

    # create a new document for summary and delete originals
    doc = models.LearningDocument(
        user_id=user_id,
        source="user_pref",
        reference_type="summary",
        reference_id=None,
        title="Auto-summarized preferences",
        content=summary,
        metadata_={"priority": 0.9, "auto_summarized": True},
    )
    db.add(doc)

    vector_store_obj = vector_store
    db.flush()
    try:
        embeddings = vector_store_obj.encode([doc.content])
        from services.vector_store import VectorItem

        vid = f"user-pref-{doc.id}"
        item = VectorItem(vector_id=vid, content=doc.content, metadata={"user_id": user_id, "document_id": doc.id, "source": doc.source})
        vector_store_obj.upsert([item], embeddings=embeddings)
    except Exception:
        pass

    for d in take:
        try:
            db.delete(d)
        except Exception:
            pass

    db.commit()


def _prune_all_users_loop(interval_seconds: int):
    while True:
        try:
            db = database.SessionLocal()
            vector_store = get_vector_store()
            users = db.query(models.User.id).all()
            for (uid,) in users:
                try:
                    prune_user_memory(db, vector_store, uid)
                    summarize_user_memory(db, vector_store, uid)
                except Exception:
                    pass
            db.close()
        except Exception:
            pass
        time.sleep(interval_seconds)


def start_background_prune_scheduler(interval_seconds: int = PRUNE_INTERVAL_SECONDS):
    """Start a background thread to prune user memories periodically."""
    t = threading.Thread(target=_prune_all_users_loop, args=(interval_seconds,), daemon=True)
    t.start()
    return t
