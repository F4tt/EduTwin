from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import models, database
from core.study_constants import (
    SUBJECTS,
    GRADE_ORDER,
    SEMESTER_ORDER,
    GRADE_DISPLAY,
    SEMESTER_DISPLAY,
)
from ml import prediction_service
from services import learning_documents
from services.vector_store_provider import get_vector_store
from services.chatbot_service import generate_chat_response
from utils.session_utils import require_auth, get_current_user, SessionManager

router = APIRouter(prefix="/study", tags=["Study"])


def build_structure() -> Dict[str, Dict[str, List[str]]]:
    structure: Dict[str, Dict[str, List[str]]] = {}
    for grade in GRADE_ORDER:
        structure[grade] = {}
        for semester in SEMESTER_ORDER[grade]:
            structure[grade][semester] = SUBJECTS.copy()
    return structure


STUDY_STRUCTURE = build_structure()


def validate_combination(grade_level: str, semester: str, subject: str) -> None:
    if grade_level not in STUDY_STRUCTURE:
        raise HTTPException(status_code=400, detail="Khối lớp không hợp lệ")
    if semester not in STUDY_STRUCTURE[grade_level]:
        raise HTTPException(status_code=400, detail="Học kỳ không hợp lệ")
    if subject not in STUDY_STRUCTURE[grade_level][semester]:
        raise HTTPException(status_code=400, detail="Môn học không hợp lệ")


class ScoreRecord(BaseModel):
    subject: str
    grade_level: str
    semester: str
    score: float

    @field_validator("grade_level")
    @classmethod
    def normalize_grade(cls, v: str) -> str:
        grade = str(v).upper()
        return grade

    @field_validator("semester")
    @classmethod
    def normalize_semester(cls, v: str) -> str:
        return str(v).upper()

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, v: str) -> str:
        return v.strip()

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        if v < 0 or v > 10:
            raise ValueError("Điểm phải nằm trong khoảng 0-10")
        return v


class ScoreBulkPayload(BaseModel):
    scores: List[ScoreRecord]


class ScoreDeleteRecord(BaseModel):
    subject: str
    grade_level: str
    semester: str


class ScoreDeletePayload(BaseModel):
    scores: List[ScoreDeleteRecord]


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/embeddings/rebuild")
@require_auth
def rebuild_all_embeddings(request: Request, db: Session = Depends(get_db)):
    """Rebuild all score embeddings into the vector store. Protected endpoint (auth required)."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    vector_store = get_vector_store()
    try:
        # reset vector store then rebuild from DB
        vector_store.reset()
    except Exception as exc:
        # continue to attempt rebuild
        print(f"Error resetting vector store: {exc}")

    learning_documents.rebuild_all_score_embeddings(db, vector_store)
    db.commit()
    return {"message": "Đã xây dựng lại embeddings cho tất cả điểm."}


@router.get("/scores")
@require_auth
def get_scores(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = user_session.get("user_id")
    rows = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    row_map = {
        (row.subject, row.grade_level, row.semester): row
        for row in rows
    }

    scores_output = []
    actual_count = 0

    for grade in GRADE_ORDER:
        for semester in SEMESTER_ORDER[grade]:
            for subject in STUDY_STRUCTURE[grade][semester]:
                key = f"{subject}_{semester}_{grade}"
                row = row_map.get((subject, grade, semester))
                actual = row.actual_score if row else None
                predicted = row.predicted_score if row else None
                if actual is not None:
                    actual_count += 1

                scores_output.append(
                    {
                        "key": key,
                        "subject": subject,
                        "grade_level": grade,
                        "semester": semester,
                        "actual": actual,
                        "predicted": predicted,
                        "actual_source": row.actual_source if row else None,
                        "predicted_source": row.predicted_source if row else None,
                    }
                )

    return {
        "scores": scores_output,
        "actual_count": actual_count,
        "grade_display": GRADE_DISPLAY,
        "semester_display": SEMESTER_DISPLAY,
        "prediction_threshold_min": 5,
        "prediction_threshold_max": 30,
    }


@router.post("/scores/bulk")
@require_auth
def upsert_scores(request: Request, payload: ScoreBulkPayload, db: Session = Depends(get_db)):
    user_session = get_current_user(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = user_session.get("user_id")
    updates = 0
    updated_scores: List[models.StudyScore] = []

    # Build chronological ordered slots to compare positions
    ordered_slots = []
    for grade in GRADE_ORDER:
        for semester in SEMESTER_ORDER[grade]:
            ordered_slots.append((grade, semester))

    def slot_index_for_record(grade_level: str, semester: str) -> int | None:
        try:
            for idx, (g, s) in enumerate(ordered_slots):
                if g == grade_level and s == semester:
                    return idx
        except Exception:
            return None
        return None

    # determine user's current grade index
    user = db.query(models.User).filter(models.User.id == user_id).first()
    current_grade_token = getattr(user, "current_grade", None)
    def slot_index_for_token(token: str) -> int | None:
        if not token:
            return None
        try:
            parts = str(token).split("_")
            if len(parts) != 2:
                return None
            sem, gr = parts[0].upper(), parts[1]
            for idx, (g, s) in enumerate(ordered_slots):
                if g == gr and s == sem:
                    return idx
        except Exception:
            return None
        return None

    current_idx = slot_index_for_token(current_grade_token)

    skipped_future_updates = 0

    for record in payload.scores:
        grade = record.grade_level
        semester = record.semester
        subject = record.subject
        validate_combination(grade, semester, subject)

        # If user has a current grade set, ignore any incoming score records that are after that grade
        rec_idx = slot_index_for_record(grade, semester)
        if current_idx is not None and rec_idx is not None and rec_idx > current_idx:
            # skip updating scores for future grades
            skipped_future_updates += 1
            continue

        score_entry = (
            db.query(models.StudyScore)
            .filter(
                models.StudyScore.user_id == user_id,
                models.StudyScore.grade_level == grade,
                models.StudyScore.semester == semester,
                models.StudyScore.subject == subject,
            )
            .first()
        )

        if not score_entry:
            score_entry = models.StudyScore(
                user_id=user_id,
                grade_level=grade,
                semester=semester,
                subject=subject,
            )
            db.add(score_entry)

        score_entry.actual_score = record.score
        score_entry.actual_source = "user_input"
        score_entry.actual_status = "confirmed"
        score_entry.actual_updated_at = datetime.utcnow()
        updates += 1
        updated_scores.append(score_entry)

    vector_store = get_vector_store()
    sync_candidates: List[models.StudyScore] = list(updated_scores)
    predicted_scores = prediction_service.update_predictions_for_user(db, user_id)
    sync_candidates.extend(predicted_scores)

    if sync_candidates:
        db.flush()
        learning_documents.sync_score_embeddings(db, vector_store, sync_candidates)

    # If the user has a current grade index, clear any actual scores that are in later slots
    if current_idx is not None:
        # build key -> index map
        key_to_idx = {}
        for idx, (g, s) in enumerate(ordered_slots):
            for subj in STUDY_STRUCTURE[g][s]:
                key = f"{subj}_{s}_{g}"
                key_to_idx[key] = idx

        rows_to_clear = (
            db.query(models.StudyScore)
            .filter(models.StudyScore.user_id == user_id)
            .all()
        )
        cleared = 0
        for r in rows_to_clear:
            key = f"{r.subject}_{r.semester}_{r.grade_level}"
            idx = key_to_idx.get(key)
            if idx is not None and idx > current_idx and r.actual_score is not None:
                r.actual_score = None
                r.actual_source = None
                r.actual_status = None
                r.actual_updated_at = None
                cleared += 1
        if cleared:
            # add cleared rows to sync so embeddings update
            learning_documents.sync_score_embeddings(db, vector_store, rows_to_clear)

    # Also update a user-level vector representing profile + scores for RAG
    try:
        db.commit()
        # build a compact text summary of user's study state
        user_scores = (
            db.query(models.StudyScore)
            .filter(models.StudyScore.user_id == user_id)
            .all()
        )
        parts = []
        for s in user_scores:
            if s.actual_score is not None:
                parts.append(f"{s.subject} {s.semester}/{s.grade_level}: {s.actual_score}")
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            parts.insert(0, f"User {user.id} {user.first_name or ''} {user.last_name or ''}")
        user_text = "\n".join(parts) if parts else f"User {user_id} - no scores"
        from services.vector_store import VectorItem
        # encode and upsert user vector
        try:
            item = VectorItem(vector_id=f"user-{user_id}", content=user_text, metadata={"user_id": user_id, "type": "user_profile"})
            vector_store.upsert([item])
        except Exception:
            pass
    except Exception:
        db.rollback()
        raise

    return {"updated": updates}


@router.post("/scores/delete")
@require_auth
def delete_scores(request: Request, payload: ScoreDeletePayload, db: Session = Depends(get_db)):
    """Clear actual score fields for the given user-owned score records."""
    user_session = get_current_user(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = user_session.get("user_id")
    deleted = 0
    deleted_rows: List[models.StudyScore] = []
    for record in payload.scores:
        try:
            validate_combination(record.grade_level, record.semester, record.subject)
        except HTTPException:
            continue

        score_entry = (
            db.query(models.StudyScore)
            .filter(
                models.StudyScore.user_id == user_id,
                models.StudyScore.grade_level == record.grade_level,
                models.StudyScore.semester == record.semester,
                models.StudyScore.subject == record.subject,
            )
            .first()
        )

        if score_entry and score_entry.actual_score is not None:
            score_entry.actual_score = None
            score_entry.actual_source = None
            score_entry.actual_status = None
            score_entry.actual_updated_at = None
            deleted += 1
            deleted_rows.append(score_entry)

    if deleted_rows:
        vector_store = get_vector_store()
        try:
            db.flush()
            # recompute predictions and sync embeddings for cleared rows
            predicted_scores = prediction_service.update_predictions_for_user(db, user_id)
            learning_documents.sync_score_embeddings(db, vector_store, deleted_rows + predicted_scores)
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {"deleted": deleted}


@router.post("/generate-slide-comments")
@router.post("/generate-slide-comments")
@require_auth
async def generate_slide_comments(request: Request, db: Session = Depends(get_db)):
    """Generate LLM comments for each data visualization slide based on current user scores.
    Comments are stored in LearningDocument metadata and returned for display in frontend.
    """
    # `require_auth` decorator populates `request.state.current_user`
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = current_user.get("user_id")
    
    # Fetch all scores for this user
    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    
    if not scores:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu điểm để sinh nhận xét")

    # Define slide types and their content
    slides = {
        "Chung": "Tổng quan chung về kết quả học tập của học sinh",
        "Khối XH": "Kết quả các môn Toán, Văn, Anh, Sử, Địa, GD công dân",
        "Khối TN": "Kết quả các môn Toán, Văn, Anh, Lý, Hóa, Sinh",
        "Từng Khối Thi": "Kết quả theo các khối thi A00, B00, C00, D01",
        "Từng Môn": "Chi tiết kết quả từng môn học",
    }

    comments = {}
    
    # Build current scores summary for context
    score_summary = "Điểm học tập hiện tại của học sinh:\n"
    for score in scores:
        if score.actual_score is not None:
            score_summary += f"- {score.subject} ({score.semester}/{score.grade_level}): {score.actual_score:.1f}\n"
    
    # Generate comment for each slide
    for slide_name, slide_desc in slides.items():
        prompt = f"""Bạn là giáo viên. Dựa trên thông tin học tập sau, hãy viết một nhận xét ngắn (2-3 câu) bằng tiếng Việt về {slide_name.lower()} của học sinh. Nhận xét phải cụ thể, tích cực, và có gợi ý cải thiện nếu cần.

Mô tả slide: {slide_desc}

{score_summary}

Nhận xét ngắn gọn, không cần lặp lại danh sách điểm:"""

        try:
            result = await generate_chat_response(
                db=db,
                user=current_user,
                message=prompt,
                session_id=None,
            )
            comment = result.get("answer", "").strip()
            if comment:
                comments[slide_name] = comment
        except Exception as e:
            comments[slide_name] = f"Không thể sinh nhận xét: {str(e)}"

    # Store comments in database (optional: in a new table or metadata)
    # For now, return them directly to frontend
    return {
        "user_id": user_id,
        "generated_at": datetime.utcnow().isoformat(),
        "slide_comments": comments,
    }
