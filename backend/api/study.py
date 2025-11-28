from datetime import datetime
from typing import Dict, List
from collections import defaultdict
import json
import logging
import re
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

logger = logging.getLogger("uvicorn.error")

from db import models, database
from core.study_constants import (
    SUBJECTS,
    SUBJECT_DISPLAY,
    GRADE_ORDER,
    SEMESTER_ORDER,
    GRADE_DISPLAY,
    SEMESTER_DISPLAY,
)
from ml import prediction_service
from services import learning_documents
from services.vector_store_provider import get_vector_store
from services.chatbot_service import generate_chat_response
from services.ml_version_manager import ensure_user_predictions_updated
from utils.session_utils import require_auth, get_current_user

router = APIRouter(prefix="/study", tags=["Study"])


def build_structure() -> Dict[str, Dict[str, List[str]]]:
    structure: Dict[str, Dict[str, List[str]]] = {}
    for grade in GRADE_ORDER:
        structure[grade] = {}
        for semester in SEMESTER_ORDER[grade]:
            structure[grade][semester] = SUBJECTS.copy()
    return structure


STUDY_STRUCTURE = build_structure()

TERM_ORDER = [
    "1_10",
    "2_10",
    "1_11",
    "2_11",
    "1_12",
    "2_12",
]
TERM_INDEX = {token: idx for idx, token in enumerate(TERM_ORDER)}

KHOI_TN_SUBJECTS = {
    "Toan",
    "Ngu van",
    "Tieng Anh",
    "Vat ly",
    "Hoa hoc",
    "Sinh hoc",
}

KHOI_XH_SUBJECTS = {
    "Toan",
    "Ngu van",
    "Tieng Anh",
    "Lich su",
    "Dia ly",
    "Giao duc cong dan",
}

EXAM_BLOCKS = {
    "A00": ["Toan", "Vat ly", "Hoa hoc"],
    "B00": ["Toan", "Hoa hoc", "Sinh hoc"],
    "C00": ["Ngu van", "Lich su", "Dia ly"],
    "D01": ["Toan", "Ngu van", "Tieng Anh"],
}


def normalize_term_token(token: str | None) -> str | None:
    if not token:
        return None
    parts = str(token).split("_")
    if len(parts) != 2:
        return None
    semester = parts[0].upper()
    grade = parts[1]
    return f"{semester}_{grade}"


def term_index_for_token(token: str | None) -> int | None:
    normalized = normalize_term_token(token)
    if not normalized:
        return None
    return TERM_INDEX.get(normalized)


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


def build_scores_payload(db: Session, user_id: int) -> Dict[str, object]:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    rows = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    row_map = {
        (row.subject, row.grade_level, row.semester): row
        for row in rows
    }

    scores_output: List[Dict[str, object]] = []
    actual_count = 0
    term_value_map = defaultdict(list)

    for grade in GRADE_ORDER:
        for semester in SEMESTER_ORDER[grade]:
            for subject in STUDY_STRUCTURE[grade][semester]:
                key = f"{subject}_{semester}_{grade}"
                row = row_map.get((subject, grade, semester))
                actual = row.actual_score if row else None
                predicted = row.predicted_score if row else None
                if actual is not None:
                    actual_count += 1

                visible_value = actual if actual is not None else predicted
                if visible_value is not None:
                    term_key = f"{semester}_{grade}"
                    term_value_map[term_key].append(float(visible_value))

                scores_output.append(
                    {
                        "key": key,
                        "subject": subject,
                        "subject_display": SUBJECT_DISPLAY.get(subject, subject),
                        "grade_level": grade,
                        "semester": semester,
                        "actual": actual,
                        "predicted": predicted,
                        "actual_source": row.actual_source if row else None,
                        "predicted_source": row.predicted_source if row else None,
                    }
                )

    term_averages = []
    for grade in GRADE_ORDER:
        for semester in SEMESTER_ORDER[grade]:
            term_key = f"{semester}_{grade}"
            values = term_value_map.get(term_key, [])
            average = round(sum(values) / len(values), 2) if values else None
            term_averages.append(
                {
                    "term": term_key,
                    "label": term_key,
                    "average": average,
                    "count": len(values),
                }
            )

    return {
        "scores": scores_output,
        "actual_count": actual_count,
        "term_averages": term_averages,
        "current_grade": getattr(user, "current_grade", None) if user else None,
        "grade_display": GRADE_DISPLAY,
        "semester_display": SEMESTER_DISPLAY,
        "subject_display": SUBJECT_DISPLAY,
        "prediction_threshold_min": 5,
        "prediction_threshold_max": 30,
    }


@router.get("/scores")
@require_auth
def get_scores(request: Request, db: Session = Depends(get_db)):
    user_session = get_current_user(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = user_session.get("user_id")
    
    # Ensure user has latest predictions (lazy evaluation)
    ensure_user_predictions_updated(db, user_id)
    
    return build_scores_payload(db, user_id)


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


@router.post("/scores/bulk")
@require_auth
def upsert_scores(request: Request, payload: ScoreBulkPayload, db: Session = Depends(get_db)):
    """Create or update multiple score records for the authenticated user."""
    user_session = get_current_user(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = user_session.get("user_id")
    if not payload.scores:
        raise HTTPException(status_code=400, detail="Danh sách điểm trống")

    updated_rows: List[models.StudyScore] = []
    validation_errors: List[str] = []

    for idx, record in enumerate(payload.scores, start=1):
        try:
            validate_combination(record.grade_level, record.semester, record.subject)
        except HTTPException as exc:
            validation_errors.append(f"Bản ghi {idx}: {exc.detail}")
            continue

        row = (
            db.query(models.StudyScore)
            .filter(
                models.StudyScore.user_id == user_id,
                models.StudyScore.grade_level == record.grade_level,
                models.StudyScore.semester == record.semester,
                models.StudyScore.subject == record.subject,
            )
            .first()
        )
        if not row:
            row = models.StudyScore(
                user_id=user_id,
                subject=record.subject,
                grade_level=record.grade_level,
                semester=record.semester,
            )
            db.add(row)

        row.actual_score = round(float(record.score), 2)
        row.actual_source = "user_portal"
        row.actual_status = "confirmed"
        row.actual_updated_at = datetime.utcnow()
        updated_rows.append(row)

    if validation_errors and not updated_rows:
        raise HTTPException(status_code=400, detail="; ".join(validation_errors))

    prediction_updates: List[models.StudyScore] = []
    try:
        db.flush()
        logger.info(f"[BULK] Starting ML pipeline for user {user_id}, updated {len(updated_rows)} actual scores")
        prediction_updates = prediction_service.update_predictions_for_user(db, user_id) or []
        logger.info(f"[BULK] ML pipeline returned {len(prediction_updates)} prediction updates")
        
        # Flush again to assign IDs to prediction_updates before sync embeddings
        db.flush()
        
        if updated_rows or prediction_updates:
            vector_store = get_vector_store()
            learning_documents.sync_score_embeddings(db, vector_store, updated_rows + prediction_updates)
        db.commit()
        logger.info(f"[BULK] Successfully committed changes for user {user_id}")
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to upsert study scores", exc_info=exc)
        detail = validation_errors[0] if validation_errors else "Không thể lưu điểm học tập"
        raise HTTPException(status_code=500, detail=detail)

    snapshot = build_scores_payload(db, user_id)
    logger.info(f"[BULK] Built snapshot with {len(snapshot.get('scores', []))} score records for user {user_id}")

    response = {
        "updated": len(updated_rows),
        "prediction_updates": len(prediction_updates),
        "scores_snapshot": snapshot,
    }
    if validation_errors:
        response["warnings"] = validation_errors
    return response


def subject_label(subject: str) -> str:
    return SUBJECT_DISPLAY.get(subject, subject)


def format_score(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def format_term_label(term: str) -> str:
    try:
        semester, grade = term.split("_")
    except ValueError:
        return term
    sem_label = SEMESTER_DISPLAY.get(semester, f"Học kỳ {semester}")
    grade_label = GRADE_DISPLAY.get(grade, f"Lớp {grade}")
    return f"{sem_label} {grade_label}"


def collect_visible_entries(
    score_rows: List[models.StudyScore],
    current_idx: int | None,
) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    fallback_index = len(TERM_ORDER)
    for row in score_rows:
        # Skip graduation exam entries (TN_TN)
        if row.semester == 'TN' or row.grade_level == 'TN':
            continue
            
        source = "actual" if row.actual_score is not None else "predicted"
        value = row.actual_score if row.actual_score is not None else row.predicted_score
        if value is None:
            continue
        term_token = f"{row.semester}_{row.grade_level}"
        term_idx = TERM_INDEX.get(term_token, fallback_index)
        is_future = False
        if current_idx is not None:
            is_future = term_idx > current_idx
        else:
            is_future = source == "predicted"

        entries.append(
            {
                "subject": row.subject,
                "term": term_token,
                "term_index": term_idx,
                "value": float(value),
                "source": source,
                "is_future": is_future,
            }
        )
    return entries


def compute_term_series(entries: List[Dict[str, object]], subject_filter: set[str] | None = None) -> List[tuple[str, float]]:
    term_buckets: Dict[str, List[float]] = defaultdict(list)
    for entry in entries:
        if subject_filter and entry["subject"] not in subject_filter:
            continue
        term_buckets[entry["term"]].append(entry["value"])

    series: List[tuple[str, float]] = []
    for term in TERM_ORDER:
        values = term_buckets.get(term)
        if values:
            avg = round(sum(values) / len(values), 2)
            series.append((term, avg))

    # include any extra terms that may appear (e.g., TN) ordered by index then name
    extra_terms = [term for term in term_buckets if term not in TERM_INDEX]
    for term in sorted(extra_terms):
        values = term_buckets[term]
        avg = round(sum(values) / len(values), 2)
        series.append((term, avg))

    return series


def compute_subject_stats(entries: List[Dict[str, object]], subject_filter: set[str] | None = None, current_idx: int | None = None) -> Dict[str, Dict[str, float]]:
    subject_entries: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for entry in entries:
        if subject_filter and entry["subject"] not in subject_filter:
            continue
        subject_entries[entry["subject"]].append(entry)

    stats: Dict[str, Dict[str, float]] = {}
    for subject, seq in subject_entries.items():
        ordered = sorted(seq, key=lambda item: item["term_index"])
        
        # Filter to only include entries up to and including current_idx
        if current_idx is not None:
            ordered = [item for item in ordered if item["term_index"] <= current_idx]
        
        values = [item["value"] for item in ordered]
        if not values:
            continue
        avg = round(sum(values) / len(values), 2)
        trend = round(ordered[-1]["value"] - ordered[0]["value"], 2) if len(ordered) >= 2 else 0.0
        stats[subject] = {
            "average": avg,
            "latest_value": round(ordered[-1]["value"], 2),
            "latest_term": ordered[-1]["term"],
            "trend": trend,
            "max_value": round(max(values), 2),
            "min_value": round(min(values), 2),
        }
    return stats


def join_with_and(items: List[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" và {items[-1]}"


def describe_summary(avg_score: float | None, subject_stats: Dict[str, Dict[str, float]]) -> str:
    if avg_score is None or not subject_stats:
        return "Chưa có đủ dữ liệu để tổng kết chung."
    total_subjects = len(subject_stats)
    sorted_subjects = sorted(subject_stats.items(), key=lambda item: item[1]["average"], reverse=True)
    top_segments = [f"{subject_label(sub)} ({format_score(stats['average'])})" for sub, stats in sorted_subjects[:2]]
    weak_segments = [f"{subject_label(sub)} ({format_score(stats['average'])})" for sub, stats in sorted_subjects[-1:]]
    sentences = [
        f"Điểm trung bình tổng thể đang ở mức {format_score(avg_score)} trên {total_subjects} môn có dữ liệu.",
    ]
    if top_segments:
        sentences.append(f"Thế mạnh nổi bật nằm ở {join_with_and(top_segments)}.")
    if weak_segments:
        sentences.append(f"Môn cần chú ý nhất là {join_with_and(weak_segments)}.")
    return " ".join(sentences)


def describe_trend(term_series: List[tuple[str, float]], context_label: str) -> str:
    if not term_series:
        return f"Chưa có dữ liệu để phân tích xu hướng của {context_label.lower()}."
    start_term, start_value = term_series[0]
    end_term, end_value = term_series[-1]
    delta = round(end_value - start_value, 2)
    if delta > 0.3:
        movement = "tăng đều"
    elif delta < -0.3:
        movement = "giảm nhẹ"
    else:
        movement = "giữ ổn định"
    trend_sentence = (
        f"Xu hướng {movement} từ {format_term_label(start_term)} ({format_score(start_value)}) "
        f"đến {format_term_label(end_term)} ({format_score(end_value)}), chênh lệch {format_score(abs(delta))} điểm."
    )
    peak_term, peak_value = max(term_series, key=lambda item: item[1])
    if peak_term != end_term:
        trend_sentence += f" Cột mốc cao nhất thuộc {format_term_label(peak_term)} với {format_score(peak_value)} điểm."
    return trend_sentence


def describe_subject_ranking(subject_stats: Dict[str, Dict[str, float]], context_label: str) -> str:
    if not subject_stats:
        return f"Chưa có dữ liệu so sánh môn học của {context_label.lower()}."
    ordered = sorted(subject_stats.items(), key=lambda item: item[1]["average"], reverse=True)
    top = ordered[:2]
    bottom = ordered[-2:]
    top_text = join_with_and([f"{subject_label(sub)} ({format_score(stats['average'])})" for sub, stats in top])
    bottom_text = join_with_and([f"{subject_label(sub)} ({format_score(stats['average'])})" for sub, stats in bottom])
    gap = None
    if top and bottom:
        gap = round(top[0][1]["average"] - bottom[-1][1]["average"], 2)
    comparison = f"Nhóm dẫn đầu gồm {top_text}."
    if bottom_text:
        comparison += f" Nhóm cần cải thiện là {bottom_text}."
    if gap is not None and gap > 0:
        comparison += f" Khoảng cách giữa mạnh nhất và yếu nhất đang ở mức {format_score(gap)} điểm."
    return comparison


def describe_radar(subject_stats: Dict[str, Dict[str, float]], context_label: str) -> str:
    if not subject_stats:
        return f"Radar chưa có dữ liệu cho {context_label.lower()}."
    ordered = sorted(subject_stats.items(), key=lambda item: item[1]["average"], reverse=True)
    strengths = ordered[:2]
    gaps = ordered[-2:]
    strength_text = join_with_and([subject_label(sub) for sub, _ in strengths])
    gap_text = join_with_and([subject_label(sub) for sub, _ in gaps])
    strength_avg = sum(stats["average"] for _, stats in strengths) / len(strengths) if strengths else 0
    gap_avg = sum(stats["average"] for _, stats in gaps) / len(gaps) if gaps else 0
    delta = round(strength_avg - gap_avg, 2)
    sentence = f"Radar cho thấy {strength_text} đang là thế mạnh trung bình {format_score(strength_avg)}."
    if gap_text:
        sentence += f" {gap_text} thấp hơn khoảng {format_score(delta)} điểm nên cần được bổ sung thêm thời gian." 
    return sentence


def summarize_examples(
    entries: List[Dict[str, object]],
    subject_filter: set[str] | None,
    current_idx: int | None,
    limit: int = 4,
) -> tuple[List[str], List[str]]:
    filtered = [entry for entry in entries if (not subject_filter or entry["subject"] in subject_filter)]
    ordered = sorted(filtered, key=lambda item: item["term_index"])
    actual_examples: List[str] = []
    future_examples: List[str] = []
    for entry in ordered:
        label = (
            f"{subject_label(entry['subject'])} - {format_term_label(entry['term'])}: "
            f"{format_score(entry['value'])} điểm"
        )
        descriptor = " (thực tế)"
        bucket = actual_examples
        if entry.get("is_future"):
            descriptor = " (dự đoán)"
            bucket = future_examples
        elif entry.get("source") == "predicted" and current_idx is None:
            descriptor = " (dự đoán)"
            bucket = future_examples
        bucket.append(label + descriptor)
    return actual_examples[:limit], future_examples[:limit]


def extract_json_dict(text: str) -> Dict[str, object]:
    if not text:
        return {}
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def build_chart_data_for_llm(
    entries: List[Dict[str, object]],
    subject_filter: set[str] | None,
    current_idx: int | None,
    current_grade_token: str | None,
) -> Dict[str, object]:
    """
    Build RAW chart data that is ACTUALLY DISPLAYED on UI charts.
    This ensures LLM only analyzes data visible to users.
    """
    filtered_entries = [entry for entry in entries if (not subject_filter or entry["subject"] in subject_filter)]
    
    # Filter to current_idx for most charts
    if current_idx is not None:
        current_entries = [e for e in filtered_entries if e["term_index"] <= current_idx]
    else:
        current_entries = filtered_entries
    
    # 1. LineChart data: Term averages (past + future)
    term_buckets: Dict[str, List[float]] = defaultdict(list)
    for entry in filtered_entries:
        term_buckets[entry["term"]].append(entry["value"])
    
    linechart_data = []
    for term in TERM_ORDER:
        values = term_buckets.get(term)
        if values:
            avg = round(sum(values) / len(values), 2)
            term_idx = TERM_INDEX.get(term, 999)
            is_past = current_idx is None or term_idx <= current_idx
            linechart_data.append({
                "term": format_term_label(term),
                "average": avg,
                "type": "past" if is_past else "future"
            })
    
    # 2. BarChart data: Subject averages (up to current only)
    subject_buckets: Dict[str, List[float]] = defaultdict(list)
    for entry in current_entries:
        subject_buckets[entry["subject"]].append(entry["value"])
    
    barchart_data = []
    for subject in SUBJECTS:
        values = subject_buckets.get(subject)
        if values:
            avg = round(sum(values) / len(values), 2)
            barchart_data.append({
                "subject": subject_label(subject),
                "average": avg
            })
    # Sort by average descending
    barchart_data.sort(key=lambda x: x["average"], reverse=True)
    
    # 3. RadarChart data: Current term only
    radar_data = []
    if current_grade_token:
        parts = current_grade_token.split('_')
        if len(parts) == 2:
            semester, grade = parts
            for entry in filtered_entries:
                if entry["term"] == current_grade_token:
                    radar_data.append({
                        "subject": subject_label(entry["subject"]),
                        "score": entry["value"]
                    })
    
    return {
        "linechart": linechart_data,
        "barchart": barchart_data,
        "radar": radar_data,
        "current_term": format_term_label(current_grade_token) if current_grade_token else "Chưa xác định",
    }


def build_context_comment(
    entries: List[Dict[str, object]],
    subject_filter: set[str] | None,
    include_summary: bool,
    context_label: str,
    current_idx: int | None,
    current_grade_label: str,
) -> Dict[str, object]:
    filtered_entries = [entry for entry in entries if (not subject_filter or entry["subject"] in subject_filter)]
    
    # Filter to only include entries up to and including current_idx
    if current_idx is not None:
        filtered_entries = [entry for entry in filtered_entries if entry["term_index"] <= current_idx]
    
    values = [entry["value"] for entry in filtered_entries]
    avg_score = round(sum(values) / len(values), 2) if values else None
    subject_stats = compute_subject_stats(entries, subject_filter, current_idx)
    term_series = compute_term_series(entries, subject_filter)
    actual_examples, future_examples = summarize_examples(entries, subject_filter, current_idx)

    return {
        "summary": describe_summary(avg_score, subject_stats) if include_summary else None,
        "trend": describe_trend(term_series, context_label),
        "subjects": describe_subject_ranking(subject_stats, context_label),
        "radar": describe_radar(subject_stats, context_label),
        "actual_examples": actual_examples,
        "future_examples": future_examples,
        "context_label": context_label,
        "current_grade_label": current_grade_label,
    }


def classify_block_fit(avg_score: float) -> str:
    if avg_score >= 8.5:
        return "rất phù hợp"
    if avg_score >= 7.5:
        return "khá phù hợp"
    if avg_score >= 6.5:
        return "cần cân nhắc"
    return "chưa phù hợp"


def build_exam_block_insights(
    entries: List[Dict[str, object]],
    current_idx: int | None,
    current_grade_label: str,
) -> Dict[str, object]:
    block_details: Dict[str, Dict[str, object]] = {}
    ranking: List[tuple[str, float]] = []

    for block, subjects in EXAM_BLOCKS.items():
        subject_filter = set(subjects)
        subject_stats = compute_subject_stats(entries, subject_filter, current_idx)
        if not subject_stats:
            block_details[block] = {
                "comment": "Chưa có dữ liệu để đánh giá khối này.",
                "average": None,
                "actual_examples": [],
                "future_examples": [],
                "context_label": f"Khối {block}",
                "current_grade_label": current_grade_label,
            }
            continue
        subject_avgs = [stats["average"] for stats in subject_stats.values()]
        block_avg = round(sum(subject_avgs) / len(subject_avgs), 2)
        ranking.append((block, block_avg))
        ordered = sorted(subject_stats.items(), key=lambda item: item[1]["average"], reverse=True)
        best = ordered[0]
        weakest = ordered[-1]
        fit_label = classify_block_fit(block_avg)
        comment = (
            f"Khối {block} đạt trung bình {format_score(block_avg)}, nổi bật ở {subject_label(best[0])} ({format_score(best[1]['average'])}). "
            f"{subject_label(weakest[0])} ({format_score(weakest[1]['average'])}) là điểm cần củng cố để {fit_label} hơn."
        )
        actual_examples, future_examples = summarize_examples(entries, subject_filter, current_idx)
        block_details[block] = {
            "comment": comment,
            "average": block_avg,
            "best_subject": subject_label(best[0]),
            "weak_subject": subject_label(weakest[0]),
            "actual_examples": actual_examples,
            "future_examples": future_examples,
            "context_label": f"Khối {block}",
            "current_grade_label": current_grade_label,
        }

    ranking = sorted([item for item in ranking if item[1] is not None], key=lambda item: item[1], reverse=True)
    if not ranking:
        headline = "Chưa đủ dữ liệu để gợi ý khối thi phù hợp."
    else:
        best_block, best_avg = ranking[0]
        runner = ranking[1] if len(ranking) > 1 else None
        fit_label = classify_block_fit(best_avg)
        best_detail = block_details.get(best_block, {})
        reason = best_detail.get("best_subject") or "các môn thế mạnh"
        headline = f"Nên ưu tiên khối {best_block} ({format_score(best_avg)}) vì {reason} đang thể hiện {fit_label}."
        if runner and runner[1] is not None:
            gap = round(best_avg - runner[1], 2)
            headline += f" Khối {runner[0]} đứng sau với mức {format_score(runner[1])}, chênh {format_score(gap)} điểm."

    return {
        "headline": headline,
        "blocks": block_details,
    }


def build_subject_comments(
    entries: List[Dict[str, object]],
    current_idx: int | None,
    current_grade_label: str,
    current_grade_token: str | None,
) -> Dict[str, Dict[str, object]]:
    subject_stats = compute_subject_stats(entries, None, current_idx)
    comments: Dict[str, Dict[str, object]] = {}
    for subject in SUBJECTS:
        stats = subject_stats.get(subject)
        if not stats:
            comments[subject] = {
                "comment": "Chưa có dữ liệu.",
                "average": None,
                "chart_data": {"linechart": []},
                "actual_examples": [],
                "future_examples": [],
                "context_label": subject_label(subject),
                "current_grade_label": current_grade_label,
            }
            continue
        
        # Build chart data for this subject (LineChart showing term progression)
        subject_entries = [e for e in entries if e["subject"] == subject]
        term_buckets: Dict[str, List[float]] = defaultdict(list)
        for entry in subject_entries:
            term_buckets[entry["term"]].append(entry["value"])
        
        linechart_data = []
        for term in TERM_ORDER:
            values = term_buckets.get(term)
            if values:
                avg = round(sum(values) / len(values), 2)
                term_idx = TERM_INDEX.get(term, 999)
                is_past = current_idx is None or term_idx <= current_idx
                linechart_data.append({
                    "term": format_term_label(term),
                    "average": avg,
                    "type": "past" if is_past else "future"
                })
        
        chart_data = {"linechart": linechart_data}
        
        trend = stats["trend"]
        if trend > 0.3:
            trend_text = "đang cải thiện"
        elif trend < -0.3:
            trend_text = "giảm nhẹ"
        else:
            trend_text = "duy trì ổn định"
        latest_label = format_term_label(stats["latest_term"])
        comment = (
            f"{subject_label(subject)} giữ trung bình {format_score(stats['average'])} và {trend_text} tới {latest_label}."
        )
        actual_examples, future_examples = summarize_examples(entries, {subject}, current_idx)
        comments[subject] = {
            "comment": comment,
            "average": stats["average"],
            "chart_data": chart_data,
            "actual_examples": actual_examples,
            "future_examples": future_examples,
            "context_label": subject_label(subject),
            "current_grade_label": current_grade_label,
        }
    return comments


@router.post("/generate-slide-comments")
@require_auth
async def generate_slide_comments(request: Request, db: Session = Depends(get_db)):
    """Build deterministic study insights for each DataViz section."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = current_user.get("user_id")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    current_grade_token = getattr(user, "current_grade", None) if user else None
    normalized_grade = normalize_term_token(current_grade_token)
    current_idx = term_index_for_token(current_grade_token)
    current_grade_label = format_term_label(normalized_grade) if normalized_grade else "Chưa thiết lập"

    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )

    if not scores:
        raise HTTPException(status_code=400, detail="Chưa có dữ liệu điểm để sinh nhận xét")

    actual_count = sum(1 for s in scores if s.actual_score is not None)
    entries = collect_visible_entries(scores, current_idx)

    if not entries:
        raise HTTPException(status_code=400, detail="Chưa có điểm thực tế hoặc dự đoán để sinh nhận xét")

    # Build RAW CHART DATA for each tab (data actually displayed on UI)
    overview_chart_data = {
        "Chung": build_chart_data_for_llm(entries, None, current_idx, current_grade_token),
        "Khối TN": build_chart_data_for_llm(entries, KHOI_TN_SUBJECTS, current_idx, current_grade_token),
        "Khối XH": build_chart_data_for_llm(entries, KHOI_XH_SUBJECTS, current_idx, current_grade_token),
    }

    exam_block_comments = build_exam_block_insights(entries, current_idx, current_grade_label)
    subject_comments = build_subject_comments(entries, current_idx, current_grade_label, current_grade_token)
    block_details = exam_block_comments.get("blocks", {})

    # Build exam block chart data (for tổ hợp tab)
    exam_blocks_chart_data = []
    for block, subjects in EXAM_BLOCKS.items():
        block_entries = [e for e in entries if e["subject"] in subjects]
        
        # Calculate TOTAL scores for LineChart (not averages)
        term_subject_scores: Dict[str, Dict[str, float]] = defaultdict(dict)
        for entry in block_entries:
            term_subject_scores[entry["term"]][entry["subject"]] = entry["value"]
        
        linechart_data = []
        for term in TERM_ORDER:
            subject_scores = term_subject_scores.get(term, {})
            # Only include if we have all 3 subjects
            if len(subject_scores) == 3:
                total = round(sum(subject_scores.values()), 2)
                term_idx = TERM_INDEX.get(term, 999)
                is_past = current_idx is None or term_idx <= current_idx
                linechart_data.append({
                    "term": format_term_label(term),
                    "total": total,
                    "type": "past" if is_past else "future"
                })
        
        # BarChart: individual subject averages (up to current)
        block_data = build_chart_data_for_llm(entries, set(subjects), current_idx, current_grade_token)
        
        exam_blocks_chart_data.append({
            "id": block,
            "subjects": [subject_label(s) for s in subjects],
            "linechart": linechart_data,
            "barchart": block_data["barchart"],
        })

    # Prepare overview payload with RAW CHART DATA
    overview_payload = [
        {
            "id": tab_name,
            "chart_data": chart_data,
        }
        for tab_name, chart_data in overview_chart_data.items()
    ]

    exam_blocks_payload = {
        "blocks": exam_blocks_chart_data,
    }

    subject_payload = [
        {
            "id": subject,
            "display": details.get("context_label"),
            "average": details.get("average"),
            "chart_data": details.get("chart_data"),
            "comment": details.get("comment"),
            "actual_examples": details.get("actual_examples"),
            "future_examples": details.get("future_examples"),
            "current_grade_label": details.get("current_grade_label"),
        }
        for subject, details in subject_comments.items()
    ]

    shared_meta = {
        "user_id": user_id,
        "current_grade_label": current_grade_label,
        "current_grade_token": current_grade_token,
        "actual_scores_count": actual_count,
    }

    async def ask_llm_for_group(title: str, instructions: List[str], data_payload: object, schema_hint: object) -> Dict[str, object]:
        """Enhanced LLM request with educational knowledge context."""
        from services.educational_knowledge import get_educational_context
        from services.dataset_analyzer import get_dataset_insights_for_llm
        
        # Add educational knowledge and dataset insights
        edu_context = get_educational_context()
        dataset_insights = get_dataset_insights_for_llm(db, current_user.get("user_id"))
        
        payload_json = json.dumps(data_payload, ensure_ascii=False, indent=2)
        schema_json = json.dumps(schema_hint, ensure_ascii=False, indent=2)
        
        context_header = [
            f"== {title} ==",
            "",
            "# KIẾN THỨC NỀN:",
            edu_context[:2500],  # Increased limit for more educational context
            ""
        ]
        
        if dataset_insights:
            context_header.extend([
                "# DỮ LIỆU THAM KHẢO:",
                dataset_insights[:1500],  # Increased limit for more benchmark data
                ""
            ])
        
        prompt = "\n".join(
            context_header
            + instructions
            + ["", "# DỮ LIỆU CẦN PHÂN TÍCH:", payload_json, "", "# YÊU CẦU ĐỊNH DẠNG:", "Trả về JSON đúng cấu trúc sau:", schema_json]
        )
        try:
            outcome = await generate_chat_response(
                db=db,
                user=current_user,
                message=prompt,
                session_id="__silent__",
            )
            answer = (outcome.get("answer") or "").strip()
        except Exception:
            answer = ""
        return extract_json_dict(answer)

    overview_instructions = [
        "Em là trợ lý học tập AI của EduTwin với kiến thức chuyên sâu về hệ thống giáo dục Việt Nam.",
        "Xưng hô: Luôn dùng 'em-bạn' (em là AI, bạn là học sinh).",
        "",
        "# QUY TẮC VÀNG - BẮT BUỘC TUÂN THỦ:",
        "1. CHỈ phân tích dữ liệu ĐƯỢC HIỂN THỊ trên chart tương ứng:",
        "   - LineChart: Chỉ nói về điểm TB theo HỌC KỲ (không nói điểm từng môn)",
        "   - BarChart: Chỉ nói về điểm TB của TỪNG MÔN cho đến hiện tại (không nói điểm tổng thể)",
        "   - RadarChart: Chỉ nói về điểm từng môn trong HỌC KỲ HIỆN TẠI",
        "2. BẮT BUỘC sử dụng KIẾN THỨC GIÁO DỤC và DỮ LIỆU THAM KHẢO (benchmark) để:",
        "   - So sánh vị trí học sinh với mặt bằng chung",
        "   - Đưa ra nhận định về mức độ (xuất sắc/giỏi/khá/trung bình/yếu)",
        "   - Gợi ý cải thiện dựa trên thống kê thực tế",
        "3. PHÂN TÍCH SÂU - Không chỉ liệt kê số liệu:",
        "   - Tìm KHÁM PHÁ: Điểm bất thường, xu hướng đặc biệt, mối tương quan",
        "   - Phân tích NGUYÊN NHÂN - HẬU QUẢ: Tại sao tăng/giảm? Ảnh hưởng gì?",
        "   - Đưa ra NHẬN ĐỊNH có GIÁ TRỊ: Quan trọng, mới mẻ, hữu ích cho học sinh",
        "",
        "# NHIỆM VỤ:",
        "Viết nhận xét chi tiết cho TỪNG TAB (Chung/Khối XH/Khối TN), mỗi tab có 4 phần: summary, trend, subjects, radar.",
        "",
        "# YÊU CẦU CHI TIẾT THEO TAB:",
        "",
        "## TAB 'CHUNG' (Tổng quan tất cả môn):",
        "",
        "### 1. SUMMARY (Phần mở đầu - 3-4 câu):",
        "- Dữ liệu: RadarChart (điểm từng môn học kỳ hiện tại) + Benchmark (so sánh mặt bằng chung)",
        "- Phân tích:",
        "  + Tính điểm TB học kỳ hiện tại từ các môn trên Radar",
        "  + SO SÁNH với benchmark: Bạn xếp top bao nhiêu %? Cao hơn/thấp hơn TB chung bao nhiêu?",
        "  + Nhận định: Xuất sắc (top 10%)/Giỏi (top 25%)/Khá (top 50%)/Trung bình/Cần cải thiện",
        "  + Phân tích điểm ĐẶC BIỆT: Có môn nào nổi bật? Có môn nào kéo điểm TB xuống?",
        "- VÍ DỤ TỐT: 'Ở học kỳ hiện tại, bạn đạt TB 8.5 trên 9 môn, cao hơn 15% so với mặt bằng chung (7.4) và nằm trong top 20% học sinh. Đặc biệt nổi bật là Toán (9.2) và Lý (8.9), trong khi GDCD (6.8) đang kéo điểm xuống.'",
        "- VÍ DỤ TỆ: 'Bạn có điểm trung bình 8.28.' (Không so sánh, không phân tích)",
        "",
        "### 2. TREND (LineChart - 4-5 câu):",
        "- Dữ liệu: CHỈ điểm TB THEO HỌC KỲ trên LineChart (VD: HK1 lớp 10: 7.8, HK2 lớp 10: 8.1, ...)",
        "- Phân tích SÂU - Không chỉ mô tả:",
        "  + XU HƯỚNG: Tăng đều/giảm dần/dao động/ổn định? Tốc độ thay đổi?",
        "  + KHÁM PHÁ: Tìm điểm BẤT THƯỜNG - học kỳ nào tăng/giảm ĐỘT NGỘT? (VD: tăng 0.8 điểm từ HK1→HK2 lớp 10)",
        "  + PHÂN TÍCH NGUYÊN NHÂN: Tại sao có biến động? (VD: Có thể do thích nghi môi trường mới, thay đổi phương pháp học)",
        "  + HẬU QUẢ: Xu hướng này ảnh hưởng gì đến mục tiêu thi đại học?",
        "  + DỰ ĐOÁN: Với xu hướng hiện tại, học kỳ tới có thể đạt bao nhiêu? (nếu có dữ liệu future)",
        "- VÍ DỤ TỐT: 'Xu hướng tăng điểm rất tích cực: từ 7.8 (HK1/10) lên 8.5 (HK1/11), tăng 0.7 điểm. Đặc biệt nổi bật là bước nhảy +0.5 điểm từ HK2/10 sang HK1/11 - có thể do bạn đã thích nghi tốt với chương trình lớp 11. Nếu duy trì, bạn có thể đạt 8.7-9.0 vào HK2/11.'",
        "- TRÁNH: Chỉ liệt kê 'điểm tăng từ 7.8 lên 8.5' mà không phân tích tại sao/ảnh hưởng gì",
        "",
        "### 3. SUBJECTS (BarChart - 4-5 câu):",
        "- Dữ liệu: CHỈ điểm TB của TỪNG MÔN (cho đến hiện tại) trên BarChart",
        "- LƯU Ý QUAN TRỌNG: BarChart hiển thị điểm TB của từng môn CHO ĐẾN HỌC KỲ HIỆN TẠI, KHÔNG phải điểm tổng thể tất cả học kỳ",
        "- Phân tích SÂU:",
        "  + PHÂN BỐ: Khoảng cách giữa môn cao nhất - thấp nhất? Cân đối hay chênh lệch lớn?",
        "  + KHÁM PHÁ: Nhóm môn nào ĐỒNG ĐỀU cao/thấp? (VD: 3 môn Tự nhiên đều >8.5 → thế mạnh khối A)",
        "  + PHÂN TÍCH THEO TỔ HỢP: So sánh TB các môn trong A00, B00, C00, D01 → tổ hợp nào phù hợp?",
        "  + NHẬN ĐỊNH GIÁ TRỊ: Môn nào là 'chìa khóa' cho mục tiêu thi đại học? Môn nào CẦN ưu tiên cải thiện?",
        "- VÍ DỤ TỐT: 'Phân bố điểm cho thấy thế mạnh rõ rệt ở khối Tự nhiên: Toán (8.9), Lý (8.7), Hóa (8.5) đều >8.5, trong khi môn Xã hội dao động 7.0-7.5. Với tổ hợp A00 (TB 8.7), bạn có lợi thế lớn cho các ngành Kỹ thuật. GDCD (7.0) đang là điểm yếu cần cải thiện để nâng GPA chung.'",
        "- TRÁNH: 'Toán cao nhất 8.9, GDCD thấp nhất 7.0' (chỉ liệt kê, không phân tích ý nghĩa)",
        "",
        "### 4. RADAR (Biểu đồ năng lực học kỳ hiện tại - 4-5 câu):",
        "- Dữ liệu: CHỈ điểm của TỪNG MÔN trong HỌC KỲ HIỆN TẠI (từ RadarChart)",
        "- Phân tích TRỰC QUAN:",
        "  + HÌNH DẠNG: Radar cân đối (hình tròn đều) → phát triển toàn diện, HAY lệch (góc nhọn) → mất cân bằng?",
        "  + ĐIỂM MẠNH: 2-3 môn có đỉnh CAO NHẤT (>8.5) → Thế mạnh cần phát huy",
        "  + ĐIỂM YẾU: 2-3 môn có đỉnh THẤP NHẤT (<7.0) → Rủi ro cần khắc phục",
        "  + SO SÁNH NHÓM: Các môn TN cao hơn XH? Hay ngược lại? → Định hướng nghề nghiệp",
        "  + PHÂN TÍCH SÂU: Độ chênh lệch giữa môn cao - thấp lớn (>2.0 điểm) → CẦN cân bằng phát triển",
        "- VÍ DỤ TỐT: 'Radar chart học kỳ này cho thấy sự PHÁT TRIỂN MẤT CÂN BẰNG: 3 môn TN (Toán 9.2, Lý 8.9, Hóa 8.7) tạo thành cụm đỉnh cao bên phải, trong khi 3 môn XH (Sử 7.2, Địa 7.0, GDCD 6.8) thấp hơn 2+ điểm. Điều này khẳng định rõ năng khiếu Tự nhiên của bạn - hãy tập trung vào tổ hợp A00/B00 thay vì cố gắng cân bằng tất cả môn.'",
        "- TRÁNH: 'Toán cao nhất, GDCD thấp nhất' (không phân tích hình dạng, ý nghĩa)",
        "",
        "## TAB 'KHỐI TN' / 'KHỐI XH':",
        "- Cấu trúc: Giống tab Chung nhưng CHỈ tập trung vào 6 môn thuộc khối",
        "- Khác biệt:",
        "  + SUMMARY: Đánh giá riêng về năng lực khối TN/XH, so sánh với benchmark riêng của khối",
        "  + TREND: Xu hướng của khối này qua các học kỳ, nhận định về sự phù hợp",
        "  + SUBJECTS: Phân tích sâu hơn về 6 môn, gợi ý tổ hợp cụ thể (A00/A01 cho TN, C00/D01 cho XH)",
        "  + Bổ sung: Hướng nghiệp (Kỹ thuật/Y Dược cho TN, Kinh tế/Luật cho XH)",
        "",
        "# LƯU Ý QUAN TRỌNG:",
        "- Xưng hô: em-bạn (em là AI, bạn là học sinh) - KHÔNG thay đổi",
        "- LUÔN phân biệt điểm thực tế (actual) và dự đoán (predicted)",
        "- BẮT BUỘC sử dụng BENCHMARK và KIẾN THỨC GIÁO DỤC từ context đã cung cấp",
        "- Không chỉ LIỆT KÊ số liệu - phải PHÂN TÍCH NGUYÊN NHÂN, HẬU QUẢ, GIÁ TRỊ",
        "- Tìm KHÁM PHÁ mới, NHẬN ĐỊNH quan trọng - giúp học sinh hiểu rõ bản thân",
        "- Thang điểm tham khảo: 9.0+ (Xuất sắc), 8.0-8.9 (Giỏi), 6.5-7.9 (Khá), 5.0-6.4 (Trung bình), <5.0 (Yếu)",
        "- Học trình: HK1 lớp 10 → HK2 lớp 12 (6 học kỳ)",
        "",
        "Trả về JSON có mảng 'tabs', mỗi phần tử gồm: id, summary, trend, subjects, radar.",
    ]

    exam_instructions = [
        "Em là trợ lý học tập AI của EduTwin với kiến thức về các khối thi đại học và tuyển sinh.",
        "Xưng hô: em-bạn (em là AI, bạn là học sinh).",
        "",
        "# QUY TẮC VÀNG:",
        "1. CHỈ sử dụng dữ liệu ĐƯỢC HIỂN THỊ trên LineChart và BarChart của từng tổ hợp",
        "2. BẮT BUỘC kết hợp KIẾN THỨC GIÁO DỤC + DỮ LIỆU BENCHMARK để:",
        "   - So sánh điểm với điểm chuẩn các trường/ngành",
        "   - Đánh giá cơ hội đỗ đại học thực tế",
        "   - Gợi ý ngành học/trường phù hợp cụ thể",
        "3. PHÂN TÍCH SÂU - không chỉ liệt kê số liệu:",
        "   - Tìm KHÁM PHÁ: Tổ hợp nào TIỀM NĂNG nhất? Tại sao?",
        "   - Phân tích NGUYÊN NHÂN - HẬU QUẢ của xu hướng điểm",
        "   - Đưa ra NHẬN ĐỊNH GIÁ TRỊ cho quyết định chọn tổ hợp",
        "",
        "# NHIỆM VỤ:",
        "1. Viết HEADLINE tổng quát (3-4 câu) - gợi ý khối thi phù hợp NHẤT",
        "2. Viết nhận xét CHI TIẾT cho TỪNG KHỐI THI (A00, B00, C00, D01)",
        "",
        "# YÊU CẦU CHO HEADLINE (3-4 câu):",
        "- Dữ liệu: So sánh điểm TB của 4 khối từ BarChart + Benchmark điểm chuẩn",
        "- Phân tích:",
        "  + XẾP HẠNG: Khối nào TIỀM NĂNG nhất (điểm cao + xu hướng tốt)?",
        "  + SO SÁNH BENCHMARK: Khối nào có cơ hội ĐỖ ĐẠI HỌC cao (>= điểm chuẩn)?",
        "  + GỢI Ý CHÍNH: 1-2 khối NÊN ưu tiên + lý do CỤ THỂ",
        "  + CẢNH BÁO (nếu có): Khối nào KHÔNG nên chọn do điểm yếu",
        "- VÍ DỤ TỐT: 'Khối A00 là lựa chọn TỐI ƯU với điểm TB 26.1 (Toán 8.9, Lý 8.7, Hóa 8.5) - cao hơn điểm chuẩn trung bình ngành Kỹ thuật 1.5 điểm. Khối B00 cũng tiềm năng (25.8) cho Y Dược. Tránh D01 do Văn chỉ 7.2, thấp hơn yêu cầu Kinh tế 0.8 điểm.'",
        "",
        "# YÊU CẦU CHO MỖI KHỐI THI (4-5 câu):",
        "",
        "## Câu 1-2: ĐÁNH GIÁ HIỆN TRẠNG + SO SÁNH BENCHMARK:",
        "- Dữ liệu: Điểm TB 3 môn trong khối (từ BarChart) + Benchmark điểm chuẩn",
        "- Phân tích:",
        "  + Tính TỔNG ĐIỂM khối = Tổng điểm 3 môn (VD: Toán 8.9 + Lý 8.7 + Hóa 8.5 = 26.1)",
        "  + Đánh giá mức độ: Xuất sắc (27+), Tốt (24-27), Khá (20-24), Trung bình (18-20), Yếu (<18)",
        "  + SO SÁNH điểm chuẩn: Cao hơn/thấp hơn bao nhiêu so với điểm chuẩn TB ngành?",
        "  + CƠ HỘI ĐỖ: Có thể đỗ trường/ngành nào? (Dựa vào benchmark)",
        "  + Liên hệ ngành học: Khối này phù hợp với ngành gì? (VD: A00→Kỹ thuật, B00→Y)",
        "",
        "## Câu 3: PHÂN TÍCH XU HƯỚNG + DỰ ĐOÁN:",
        "- Dữ liệu: LineChart hiển thị TỔNG ĐIỂM khối qua các học kỳ (VD: HK1/10: 24.2, HK2/10: 25.1, HK1/11: 26.1)",
        "- LƯU Ý: LineChart của khối thi hiển thị TỔNG ĐIỂM (không phải trung bình) để dễ so sánh với điểm chuẩn",
        "- Phân tích:",
        "  + Xu hướng tăng/giảm? Tốc độ thay đổi? (VD: tăng 1.9 điểm từ HK1/10 đến HK1/11)",
        "  + NGUYÊN NHÂN: Môn nào đóng góp chính vào sự tăng/giảm?",
        "  + DỰ ĐOÁN: Với xu hướng này, tổng điểm thi thực tế có thể đạt bao nhiêu?",
        "  + HẬU QUẢ: Ảnh hưởng đến cơ hội đỗ như thế nào? (VD: Từ 26.1 → dự đoán 27+ → Đủ sức thi ĐHBK)",
        "",
        "## Câu 4-5: ĐIỂM MẠNH - ĐIỂM YẾU + KẾT LUẬN:",
        "- Dữ liệu: Điểm của TỪNG MÔN trong khối (từ BarChart)",
        "- Phân tích:",
        "  + MÔN MẠNH: Môn nào GÓP PHẦN lớn vào điểm khối? Nên phát huy như thế nào?",
        "  + MÔN YẾU: Môn nào KÉO ĐIỂM xuống? Cần cải thiện bao nhiêu để an toàn?",
        "  + ĐỘ CHÊNH LỆCH: Lớn (>1.5 điểm) → Cần cân bằng; Nhỏ (<0.5) → Đồng đều tốt",
        "  + KẾT LUẬN: NÊN/KHÔNG NÊN chọn tổ hợp? Lý do CỤ THỂ + Hành động cần làm",
        "",
        "# VÍ DỤ TỐT (Khối A00):",
        "\"Khối A00 là ĐIỂM SÁNG với tổng 26.1 điểm (Toán 8.9, Lý 8.7, Hóa 8.5) - vượt điểm chuẩn Bách Khoa 1.8 điểm, mở ra cơ hội đỗ các ngành Kỹ thuật hàng đầu như ĐHBK Hà Nội (24.5), ĐHQG (25.0). \"",
        "\"Xu hướng tăng mạnh từ 24.2 (HK1/10) lên 26.1 (HK1/11, +1.9 điểm) cho thấy bạn đang phát triển xuất sắc - nếu duy trì, có thể đạt 27+ vào HK2/12, đủ sức thi các trường TOP. \"",
        "\"Toán (8.9) và Lý (8.7) là 2 trụ cột vững chắc, nhưng Hóa (8.5) vẫn có thể nâng lên 9.0 để tối ưu điểm khối. \"",
        "\"KẾT LUẬN: Khối A00 là LỰA CHỌN TỐI ƯU - hãy tập trung ôn luyện Hóa học thêm 0.5 điểm để đảm bảo 27+ điểm tổng, tăng cơ hội đỗ các trường top 5 quốc gia.\"",
        "",
        "# VÍ DỤ TỆ (TRÁNH):",
        "\"Khối A00 có điểm trung bình 8.7. Toán cao nhất, Hóa thấp nhất.\" (Chỉ liệt kê, không so sánh benchmark, không phân tích giá trị)",
        "",
        "# KIẾN THỨC VỀ CÁC KHỐI:",
        "- A00 (Toán-Lý-Hóa): Kỹ thuật, Công nghệ, Kiến trúc, Xây dựng (Điểm chuẩn TB: 22-26)",
        "- A01 (Toán-Lý-Anh): Kỹ thuật quốc tế, CNTT (Điểm chuẩn TB: 23-27)",
        "- B00 (Toán-Hóa-Sinh): Y Dược, Sinh học, Nông nghiệp (Điểm chuẩn TB: 24-28)",
        "- C00 (Văn-Sử-Địa): Khoa học xã hội, Giáo dục, Báo chí (Điểm chuẩn TB: 20-24)",
        "- D01 (Toán-Văn-Anh): Kinh tế, Ngoại ngữ, Quản trị (Điểm chuẩn TB: 22-26)",
        "",
        "# LƯU Ý:",
        "- Xưng hô: em-bạn (không thay đổi)",
        "- BẮT BUỘC sử dụng BENCHMARK và KIẾN THỨC GIÁO DỤC từ context",
        "- Không chỉ LIỆT KÊ - phải PHÂN TÍCH NGUYÊN NHÂN, HẬU QUẢ, GIÁ TRỊ",
        "- Đưa ra GỢI Ý CỤ THỂ: Trường nào? Ngành gì? Cần cải thiện bao nhiêu?",
        "",
        "Trả về JSON có 'headline' (string) và mảng 'blocks' với mỗi phần tử gồm: id, comment.",
    ]

    subject_instructions = [
        "Em là trợ lý học tập AI của EduTwin.",
        "Xưng hô: em-bạn (em là AI, bạn là học sinh).",
        "",
        "# NHIỆM VỤ:",
        "Viết nhận xét NGẮN GỌN (1-2 câu) cho TỪNG MÔN HỌC dựa trên LineChart (xu hướng qua các học kỳ)",
        "",
        "# DỮ LIỆU:",
        "- LineChart: Điểm TB của môn qua các học kỳ (VD: HK1/10: 7.5, HK2/10: 7.8, HK1/11: 8.2, ...)",
        "- Actual_examples: Điểm thực tế đã có",
        "- Future_examples: Điểm dự đoán (nếu có)",
        "",
        "# CẤU TRÚC NHẬN XÉT (1-2 câu NGẮN GỌN):",
        "",
        "## Câu 1: XU HƯỚNG + PHÂN TÍCH:",
        "- Mô tả xu hướng từ LineChart (tăng đều/giảm/dao động/ổn định)",
        "- Phân tích điểm NỔI BẬT: Học kỳ nào tăng/giảm nhiều nhất? Nguyên nhân có thể?",
        "- So sánh: Điểm hiện tại vs điểm đầu - thay đổi bao nhiêu?",
        "",
        "## Câu 2 (TÙY CHỌN): NHẬN ĐỊNH + GỢI Ý:",
        "- Nếu xu hướng TỐT (tăng đều): Khích lệ duy trì",
        "- Nếu xu hướng XẤU (giảm hoặc dao động): Gợi ý cải thiện NGẮN GỌN",
        "- Nếu có dự đoán future: Nhận xét về điểm dự đoán",
        "",
        "# VÍ DỤ TỐT:",
        "- \"Toán tăng ổn định từ 7.5 (HK1/10) lên 8.7 (HK1/11), đặc biệt bứt phá +0.6 điểm ở HK1/11 - có thể do thích nghi tốt chương trình lớp 11. Duy trì phương pháp này, bạn có thể đạt 9.0+ vào cuối năm.\"",
        "- \"Hóa học dao động 7.2-7.8 qua 4 học kỳ, chưa có xu hướng rõ ràng. Hãy xem lại phương pháp học để tạo bước tiến đột phá.\"",
        "- \"GDCD ổn định quanh 7.0 (±0.2) - đủ qua môn nhưng chưa nổi bật. Tăng thêm 0.5-1.0 điểm sẽ cải thiện đáng kể GPA chung.\"",
        "",
        "# VÍ DỤ TỆ (TRÁNH):",
        "- \"Toán giữ trung bình 8.5 và đang cải thiện tới HK1 lớp 11.\" (Quá chung chung, không phân tích)",
        "- \"Bạn đang học tốt môn Toán.\" (Không có số liệu, không có giá trị)",
        "",
        "# LƯU Ý:",
        "- NGẮN GỌN: Chỉ 1-2 câu, tập trung vào PHÂN TÍCH xu hướng từ LineChart",
        "- PHẢI nêu rõ điểm là thực tế (actual) hay dự đoán (predicted)",
        "- SỬ DỤNG số liệu cụ thể từ chart_data.linechart",
        "- PHÂN TÍCH NGUYÊN NHÂN khi có biến động bất thường",
        "- KHÔNG chỉ mô tả - phải có NHẬN ĐỊNH có giá trị",
        "",
        "Trả về JSON có mảng 'subjects' với mỗi phần tử gồm: id, comment.",
    ]

    overview_schema = {
        "tabs": [
            {
                "id": "Chung",
                "summary": "",
                "trend": "",
                "subjects": "",
                "radar": "",
            }
        ]
    }
    exam_schema = {
        "headline": "",
        "blocks": [
            {
                "id": "A00",
                "comment": "",
            }
        ],
    }
    subject_schema = {
        "subjects": [
            {
                "id": "Toan",
                "comment": "",
            }
        ]
    }

    overview_response = await ask_llm_for_group(
        "Nhận xét tổng quan",
        overview_instructions,
        {"meta": shared_meta, "tabs": overview_payload},
        overview_schema,
    )
    exam_response = await ask_llm_for_group(
        "Đánh giá khối thi",
        exam_instructions,
        {"meta": shared_meta, **exam_blocks_payload},
        exam_schema,
    )
    subject_response = await ask_llm_for_group(
        "Nhận xét từng môn",
        subject_instructions,
        {"meta": shared_meta, "subjects": subject_payload},
        subject_schema,
    )

    ai_response = {
        "overview_tabs": overview_response.get("tabs"),
        "exam_blocks": exam_response,
        "subjects": subject_response.get("subjects"),
    }

    def index_by_id(items: object) -> Dict[str, Dict[str, object]]:
        mapping: Dict[str, Dict[str, object]] = {}
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    key = item.get("id")
                    if isinstance(key, str):
                        mapping[key] = item
        return mapping

    def pick_text(primary: object, fallback: object) -> str | None:
        if isinstance(primary, str) and primary.strip():
            return primary.strip()
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()
        return None

    overview_ai_map = index_by_id(ai_response.get("overview_tabs"))
    exam_ai = ai_response.get("exam_blocks") if isinstance(ai_response.get("exam_blocks"), dict) else {}
    exam_block_ai_map = index_by_id(exam_ai.get("blocks")) if isinstance(exam_ai, dict) else {}
    subject_ai_map = index_by_id(ai_response.get("subjects"))

    # Build overview comments from AI response
    overview_llm: Dict[str, Dict[str, str]] = {}
    for tab_name in ["Chung", "Khối TN", "Khối XH"]:
        ai_section = overview_ai_map.get(tab_name, {})
        overview_llm[tab_name] = {
            "summary": ai_section.get("summary", ""),
            "trend": ai_section.get("trend", ""),
            "subjects": ai_section.get("subjects", ""),
            "radar": ai_section.get("radar", ""),
        }

    exam_headline_text = ""
    if isinstance(exam_ai, dict):
        exam_headline_text = exam_ai.get("headline", "")

    exam_block_llm: Dict[str, Dict[str, str]] = {}
    for block in EXAM_BLOCKS.keys():
        block_payload = exam_block_ai_map.get(block, {})
        exam_block_llm[block] = {
            "comment": block_payload.get("comment", "")
        }

    subject_llm: Dict[str, Dict[str, str]] = {}
    for subject in SUBJECTS:
        ai_comment = subject_ai_map.get(subject, {}).get("comment", "")
        subject_llm[subject] = {
            "comment": ai_comment
        }

    warning = None
    if actual_count < 5:
        warning = {"level": "danger", "message": "Chưa đủ thông tin để đưa ra dự đoán"}
    elif 5 <= actual_count <= 20:
        warning = {"level": "info", "message": "KNN đã kích hoạt — bổ sung càng nhiều điểm để tăng độ chính xác"}

    resp = {
        "user_id": user_id,
        "generated_at": datetime.utcnow().isoformat(),
        "comments_version": 3,
        "slide_comments": {
            "overview": {
                name: {
                    "narrative": overview_llm.get(name),
                }
                for name in ["Chung", "Khối TN", "Khối XH"]
            },
            "exam_blocks": {
                "headline": {
                    "narrative": {"headline": exam_headline_text} if exam_headline_text else None,
                },
                "blocks": {
                    block: {
                        "narrative": exam_block_llm.get(block),
                    }
                    for block in EXAM_BLOCKS.keys()
                },
            },
            "subjects": {
                subject: {
                    "narrative": subject_llm.get(subject),
                }
                for subject in SUBJECTS
            },
        },
    }
    if warning is not None:
        resp["warning"] = warning
    return JSONResponse(content=resp)
