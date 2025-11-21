from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, Request, Body
from sqlalchemy.orm import Session

from db import database, models
from ml import prediction_service
from services import excel_importer, learning_documents
from services.vector_store_provider import get_vector_store
from services.llm_provider import get_llm_provider
from utils.session_utils import get_current_user, require_auth

router = APIRouter(prefix="/developer", tags=["Developer"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_developer(user: dict | None) -> None:
    if not user or user.get("role") not in {"developer", "admin"}:
        raise HTTPException(status_code=403, detail="Chỉ developer mới được phép truy cập tính năng này.")


@router.post("/import-excel")
@require_auth
async def import_excel_data(
    request: Request,
    db: Session = Depends(get_db),
    file = File(...),
):
    user = get_current_user(request)
    _ensure_developer(user)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="File rỗng.")

    summary = excel_importer.import_knn_reference_dataset(
        db,
        file_bytes=contents,
        filename=file.filename or "knn_reference.xlsx",
        uploader_id=user.get("user_id"),
    )

    vector_store = get_vector_store()
    scores_to_sync = []
    user_ids = [row[0] for row in db.query(models.User.id).all()]
    for user_id in user_ids:
        updates = prediction_service.update_predictions_for_user(db, user_id)
        if updates:
            scores_to_sync.extend(updates)

    if scores_to_sync:
        db.flush()
        learning_documents.sync_score_embeddings(db, vector_store, scores_to_sync)
    db.commit()

    return {"summary": asdict(summary)}


@router.post("/rebuild-embeddings")
@require_auth
def rebuild_embeddings(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request)
    _ensure_developer(user)

    vector_store = get_vector_store()
    learning_documents.rebuild_all_score_embeddings(db, vector_store)
    db.commit()
    return {"message": "Đã tái xây dựng vector database từ dữ liệu hiện có."}


@router.post("/llm-test")
async def llm_test(payload: dict = Body(...)):
    """Temporary unauthenticated endpoint for quickly testing LLM connectivity.
    WARNING: This endpoint is for local development only. It should be removed or guarded in production.
    """
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' in request body.")

    provider = get_llm_provider()

    # build a minimal system + user message list
    system = {
        "role": "system",
        "content": "Bạn là trợ lý. Trả lời ngắn gọn, bằng tiếng Việt. Đây là kiểm tra kết nối LLM."
    }
    user = {"role": "user", "content": message}
    try:
        resp = await provider.chat(messages=[system, user], temperature=0.2)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")

    # best-effort extraction of first reasonable text
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

    answer = None
    if isinstance(resp, dict):
        # try common places
        choices = resp.get("choices")
        if isinstance(choices, list) and choices:
            c0 = choices[0]
            if isinstance(c0, dict):
                msg = c0.get("message") or {}
                answer = msg.get("content") if isinstance(msg, dict) else None
                if not answer and isinstance(c0.get("text"), str):
                    answer = c0.get("text")
        if not answer:
            out = resp.get("outputs") or resp.get("predictions") or resp.get("candidates")
            ans = _scan(out) if out else None
            if ans:
                answer = ans
        if not answer:
            answer = _scan(resp)

    return {"raw": resp, "answer": answer}

