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
# REMOVED: learning_documents and vector_store_provider imports (no longer used)
from services.chatbot_service import generate_chat_response
from services.ml_version_manager import ensure_user_predictions_updated
from utils.session_utils import require_auth, get_current_user
from core.websocket_manager import emit_study_update, emit_prediction_update

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


class GenerateCommentsRequest(BaseModel):
    active_tab: str | None = None  # Tab đang xem: "Chung", "Khối TN", "Khối XH", "Tổ Hợp", "Từng Môn"
    persist: bool = False  # Có lưu vào database không (cho cross-device sync)


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# REMOVED: /embeddings/rebuild endpoint (vector store no longer used)


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
        # REMOVED: Vector store sync (not needed for score analytics)
        # vector_store = get_vector_store()
        try:
            db.flush()
            # recompute predictions after clearing scores
            predicted_scores = prediction_service.update_predictions_for_user(db, user_id)
            # REMOVED: learning_documents.sync_score_embeddings(db, vector_store, deleted_rows + predicted_scores)
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
        
        # Flush again to assign IDs to prediction_updates
        db.flush()
        
        # REMOVED: Vector store sync (not needed for score analytics)
        # if updated_rows or prediction_updates:
        #     vector_store = get_vector_store()
        #     learning_documents.sync_score_embeddings(db, vector_store, updated_rows + prediction_updates)
        
        db.commit()
        logger.info(f"[BULK] Successfully committed changes for user {user_id}")
        
        # Emit realtime update via WebSocket
        try:
            import asyncio
            asyncio.create_task(emit_study_update(user_id, {
                'type': 'score_update',
                'updated_count': len(updated_rows),
                'prediction_count': len(prediction_updates),
                'timestamp': datetime.utcnow().isoformat()
            }))
            asyncio.create_task(emit_prediction_update(user_id, {
                'predictions': [
                    {
                        'subject': p.subject,
                        'grade_level': p.grade_level,
                        'semester': p.semester,
                        'score': p.predicted_score
                    } for p in prediction_updates
                ],
                'timestamp': datetime.utcnow().isoformat()
            }))
        except Exception as ws_err:
            logger.warning(f"Failed to emit WebSocket updates: {ws_err}")
            
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
    """Extract JSON from LLM response, handling various formats."""
    if not text:
        return {}
    text = text.strip()
    
    # Try direct JSON parse first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Remove markdown code blocks (```json ... ``` or ``` ... ```)
    if "```" in text:
        # Extract content between ```json and ``` or ``` and ```
        import re
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    # Find JSON object in text
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
async def generate_slide_comments(
    request: Request,
    payload: GenerateCommentsRequest,
    db: Session = Depends(get_db)
):
    """Build deterministic study insights for each DataViz section.
    
    Now supports targeted analysis for specific tabs to reduce processing time and token usage.
    """
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    # Get active tab from request
    active_tab = payload.active_tab or "Chung"
    
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
            "# 📚 KIẾN THỨC NỀN VỀ HỆ THỐNG GIÁO DỤC:",
            edu_context[:2500],  # Increased - more context for deeper analysis
            ""
        ]
        
        if dataset_insights:
            context_header.extend([
                "",
                "# 📊 DỮ LIỆU THAM KHẢO & MẶT BẰNG CHUNG:",
                "BẮT BUỘC: SỬ DỤNG số liệu này để so sánh vị trí học sinh",
                dataset_insights[:2000],  # Increased - critical for benchmarking
                ""
            ])
        
        prompt = "\n".join(
            context_header
            + instructions
            + ["", "# DỮ LIỆU CẦN PHÂN TÍCH:", payload_json, "", 
               "# YÊU CẦU ĐỊNH DẠNG:", 
               "BẮT BUỘC: Trả về ĐÚNG JSON format như sau (KHÔNG thêm text nào khác):", 
               schema_json,
               "",
               "CHÚ Ý: Chỉ trả về JSON object, KHÔNG markdown, KHÔNG giải thích thêm."]
        )
        try:
            logger.info(f"[AI_ANALYSIS] Calling LLM for: {title}")
            outcome = await generate_chat_response(
                db=db,
                user=current_user,
                message=prompt,
                session_id="__silent__",
            )
            answer = (outcome.get("answer") or "").strip()
            logger.info(f"[AI_ANALYSIS] Got response for {title}, length: {len(answer)}")
            if not answer:
                logger.warning(f"[AI_ANALYSIS] Empty response for {title}")
            else:
                # Log first 500 chars of response for debugging
                logger.info(f"[AI_ANALYSIS] Response preview: {answer[:500]}")
        except Exception as e:
            logger.error(f"[AI_ANALYSIS] Error calling LLM for {title}: {e}")
            answer = ""
        result = extract_json_dict(answer)
        logger.info(f"[AI_ANALYSIS] Extracted JSON for {title}: {list(result.keys()) if result else 'empty'}")
        return result

    # Alias for single chart analysis
    ask_llm_for_chart = ask_llm_for_group
    
    def build_summary_instructions() -> List[str]:
        """Instructions for SUMMARY analysis - focuses on current position vs benchmark."""
        return [
            "Bạn là trợ lý học tập AI của EduTwin.",
            "Xưng hô: mình-bạn (mình là AI, bạn là học sinh).",
            "",
            "# NHIỆM VỤ: Viết SUMMARY (Tổng quan 4-5 câu)",
            "",
            "# DỮ LIỆU NHẬN ĐƯỢC:",
            "- linechart: Điểm TB qua các học kỳ",
            "- current_term: Học kỳ hiện tại",
            "- Benchmark từ 'DỮ LIỆU THAM KHẢO': median, p75, p90",
            "",
            "# CẤU TRÚC (4-5 câu):",
            "",
            "CÂU 1: VỊ TRÍ HIỆN TẠI + SO SÁNH BENCHMARK",
            "  - Lấy điểm TB học kỳ hiện tại: linechart → phần tử CUỐI có type='past' → field 'average'",
            "  - So sánh với benchmark: median, p75, p90",
            "  - Đánh giá: Top bao nhiêu %? Mức độ nào (Xuất sắc/Giỏi/Khá/TB)?",
            "  VD: 'Ở HK1/12, Phát Thành đạt 7.89 điểm (Khá), nằm giữa median (7.44) và p75 (8.5),",
            "       cao hơn 50% học sinh nhưng cần +0.61 điểm để vào Top 25%.'",
            "",
            "CÂU 2-3: PHÂN TÍCH NGUYÊN NHÂN",
            "  - Khoảng cách giữa cao nhất - thấp nhất?",
            "  - Ý nghĩa: Năng khiếu? Mất cân bằng?",
            "",
            "CÂU 4-5: HẬU QUẢ & HÀNH ĐỘNG",
            "  - Cơ hội đỗ đại học với vị trí này?",
            "  - Cần cải thiện bao nhiêu để đạt mục tiêu?",
            "  - Gợi ý chiến lược cụ thể",
            "",
            "QUAN TRỌNG:",
            "- PHẢI lấy điểm từ linechart, KHÔNG tự tính",
            "- PHẢI so sánh với benchmark từ DỮ LIỆU THAM KHẢO",
            "- Nêu rõ nguồn: 'LineChart cho thấy...', 'Theo benchmark...'",
            "",
            "Trả về JSON: {\"summary\": \"...\"}"
        ]
    
    def build_trend_instructions() -> List[str]:
        """Instructions for TREND analysis - focuses on changes over time."""
        return [
            "Bạn là trợ lý học tập AI của EduTwin.",
            "Xưng hô: mình-bạn (mình là AI, bạn là học sinh).",
            "",
            "# NHIỆM VỤ: Viết TREND (Xu hướng 4-5 câu)",
            "",
            "# DỮ LIỆU NHẬN ĐƯỢC:",
            "- linechart: Điểm TB qua các học kỳ (HK1/10 → HK2/10 → HK1/11 → ...)",
            "- Mỗi phần tử có: term, average, type (past/future)",
            "",
            "# CẤU TRÚC (4-5 câu):",
            "",
            "CÂU 1: MÔ TẢ XU HƯỚNG TỔNG THỂ",
            "  - Tăng/Giảm/Dao động/Ổn định? Tốc độ?",
            "  - Số liệu cụ thể: HK1/10 (X) → HK2/10 (Y) → HK1/11 (Z)",
            "  VD: 'LineChart cho thấy xu hướng TĂNG ổn định từ 7.2 (HK1/10) lên 7.89 (HK1/12),",
            "       tốc độ trung bình +0.15 điểm/kỳ.'",
            "",
            "CÂU 2-3: PHÂN TÍCH BẤT THƯỜNG & NGUYÊN NHÂN",
            "  - Học kỳ nào có biến động LỚN (tăng/giảm >0.3)?",
            "  - TẠI SAO? Nguyên nhân có thể?",
            "  - So với xu hướng chung - Bình thường hay bất thường?",
            "  VD: 'Đặc biệt, HK1/11 giảm 0.5 điểm - BẤT THƯỜNG vì đây là giai đoạn cơ bản.",
            "       Có thể do thay đổi phương pháp học hoặc tâm lý.'",
            "",
            "CÂU 4-5: DỰ ĐOÁN & HÀNH ĐỘNG",
            "  - Nếu có type='future': Đánh giá tính khả thi",
            "  - Nếu duy trì xu hướng, kết quả ra sao?",
            "  - Cần làm gì để cải thiện/duy trì?",
            "",
            "QUAN TRỌNG:",
            "- CHỈ phân tích dữ liệu trong linechart",
            "- Phân biệt rõ past (thực tế) và future (dự đoán)",
            "- Tìm QUY LUẬT, không chỉ mô tả",
            "",
            "Trả về JSON: {\"trend\": \"...\"}"
        ]
    
    def build_bars_instructions() -> List[str]:
        """Instructions for SUBJECTS analysis - focuses on comparing subjects."""
        return [
            "Bạn là trợ lý học tập AI của EduTwin.",
            "Xưng hô: mình-bạn (mình là AI, bạn là học sinh).",
            "",
            "# NHIỆM VỤ: Viết SUBJECTS (So sánh môn 4-5 câu)",
            "",
            "# DỮ LIỆU NHẬN ĐƯỢC:",
            "- barchart: Điểm TB từng môn (cho đến hiện tại)",
            "- Mỗi phần tử có: subject (tên môn), average (điểm TB)",
            "",
            "# CẤU TRÚC (4-5 câu):",
            "",
            "CÂU 1-2: PHÂN LOẠI NHÓM MÔN",
            "  - Nhóm MẠNH: Các môn cao nhất?",
            "  - Nhóm YẾU: Các môn thấp nhất?",
            "  - Độ chênh lệch giữa các nhóm?",
            "  VD: 'BarChart cho thấy SỰ PHÂN TÁCH: Khối TN tạo \"tầng cao\" (Toán 8.9, Lý 8.7, Hóa 8.5),",
            "       trong khi khối XH ở \"tầng thấp\" (Sử 7.1, Địa 6.9, GDCD 6.5). Chênh lệch 1.8-2.4 điểm.'",
            "",
            "CÂU 3-4: Ý NGHĨA & GỢI Ý",
            "  - Tổ hợp nào PHÙ HỢP nhất?",
            "  - Môn nào cần cải thiện? Cần tăng bao nhiêu?",
            "  - Chiến lược tối ưu?",
            "  VD: 'Đây là TÍN HIỆU rõ về năng khiếu TN - không phải điểm yếu XH!",
            "       Thay vì cân bằng (sai lầm), hãy tập trung A00/B00. Đẩy 3 môn TN lên 9.0+",
            "       → 27+ điểm tổng → đủ thi ĐHBK, ĐHQG.'",
            "",
            "QUAN TRỌNG:",
            "- CHỈ phân tích dữ liệu trong barchart",
            "- Tìm NHÓM, QUY LUẬT, không chỉ liệt kê",
            "- Liên hệ với TỔ HỢP thi đại học",
            "",
            "Trả về JSON: {\"subjects\": \"...\"}"
        ]
    
    def build_radar_instructions() -> List[str]:
        """Instructions for RADAR analysis - focuses on current term distribution."""
        return [
            "Bạn là trợ lý học tập AI của EduTwin.",
            "Xưng hô: mình-bạn (mình là AI, bạn là học sinh).",
            "",
            "# NHIỆM VỤ: Viết RADAR (Phân bổ điểm 4-5 câu)",
            "",
            "# DỮ LIỆU NHẬN ĐƯỢC:",
            "- radar: Điểm từng môn trong HỌC KỲ HIỆN TẠI",
            "- current_term: Học kỳ đang phân tích",
            "- Mỗi phần tử có: subject (tên môn), score (điểm)",
            "",
            "# CẤU TRÚC (4-5 câu):",
            "",
            "CÂU 1: MÔ TẢ HÌNH DẠNG RADAR",
            "  - Cân đối (tròn đều) hay mất cân bằng (góc nhọn)?",
            "  - Độ chênh cao-thấp?",
            "  VD: 'Radar HK1/12 cho thấy HÌNH DẠNG MẤT CÂN BẰNG với độ chênh 2.4 điểm.'",
            "",
            "CÂU 2: PHÂN TÍCH CỤM/NHÓM",
            "  - Môn nào tạo cụm ĐỈNH cao?",
            "  - Môn nào tạo cụm ĐÁY thấp?",
            "  - Có quy luật? (TN cao hơn XH? Tính toán cao hơn ghi nhớ?)",
            "  VD: '3 môn TN (Toán 8.9, Lý 8.7, Hóa 8.5) tạo \"cụm đỉnh\" ở góc phải,",
            "       trong khi 3 môn XH (Sử 7.1, Địa 6.9, GDCD 6.5) tạo \"cụm đáy\" ở góc trái.'",
            "",
            "CÂU 3-4: TƯƠNG QUAN & NGUYÊN NHÂN",
            "  - Tại sao các môn này cùng cao/thấp?",
            "  - Liên quan NĂNG KHIẾU? Phương pháp học? Sở thích?",
            "  - Nhất quán với xu hướng từ LineChart không?",
            "",
            "CÂU 5: KẾT LUẬN & CHIẾN LƯỢC",
            "  - Radar này cho thấy gì về BẢN THÂN học sinh?",
            "  - Nên PHÁT HUY gì? KHẮC PHỤC gì?",
            "  - Chiến lược tối ưu cho tương lai?",
            "  VD: 'Radar khẳng định năng khiếu TN rõ ràng. Thay vì cố cân bằng tất cả,",
            "       hãy ĐẨY MẠNH 3 môn TN lên 9.0+ trong 2 tháng tới để tối ưu A00/B00.'",
            "",
            "QUAN TRỌNG:",
            "- CHỈ phân tích dữ liệu trong radar (học kỳ hiện tại)",
            "- Tìm INSIGHT, TƯƠNG QUAN, không chỉ mô tả",
            "- Giải thích NGUYÊN NHÂN, HẬU QUẢ, GIÁ TRỊ",
            "",
            "Trả về JSON: {\"radar\": \"...\"}"
        ]

    def build_exam_blocks_instructions() -> List[str]:
        """Instructions for EXAM BLOCKS tab - analyzing combined subject blocks for university entrance."""
        return [
            "Bạn là trợ lý học tập AI của EduTwin.",
            "Xưng hô: mình-bạn (mình là AI, bạn là học sinh).",
            "",
            "# NHIỆM VỤ: Phân tích TOÀN DIỆN từng KHỐI THI ĐẠI HỌC",
            "",
            "# DỮ LIỆU NHẬN ĐƯỢC:",
            "- meta: current_grade_label (học kỳ hiện tại), actual_scores_count",
            "- blocks: Danh sách các khối (A00, B00, C00, D01)",
            "- Mỗi block có:",
            "  * subjects: 3 môn trong khối",
            "  * linechart: [{term, total, type='past'/'future'}] - TỔNG ĐIỂM 3 môn qua các kỳ",
            "  * barchart: [{subject, average}] - Điểm TB từng môn (đến hiện tại)",
            "- DỮ LIỆU THAM KHẢO (benchmark): median, p75, p90 của khối thi",
            "- KIẾN THỨC: Điểm chuẩn các trường, yêu cầu thi đại học",
            "",
            "# CẤU TRÚC PHÂN TÍCH CHO MỖI KHỐI (5-8 câu):",
            "",
            "## PHẦN 1: XU HƯỚNG & VỊ TRÍ HIỆN TẠI (3-4 câu)",
            "Từ LINECHART - Phân tích tổng điểm khối qua các kỳ:",
            "",
            "CÂU 1: XU HƯỚNG QUÁ KHỨ",
            "  - Tổng điểm thay đổi như thế nào từ HK1/10 đến hiện tại?",
            "  - Ổn định/Tăng/Giảm? Biến động bất thường ở kỳ nào?",
            "  VD: 'Khối A00 có xu hướng tăng ổn định từ 22.5 (HK1/10) lên 24.8 (HK1/11),",
            "       nhưng giảm xuống 23.2 ở HK2/11 (bất thường - có thể do áp lực thi cuối năm).'",
            "",
            "CÂU 2: VỊ TRÍ HIỆN TẠI + BENCHMARK",
            "  - Lấy điểm HIỆN TẠI: linechart → phần tử CUỐI có type='past' → field 'total'",
            "  - So sánh với benchmark: median, p75, p90",
            "  - Đánh giá: Top bao nhiêu %? Đủ điều kiện trường nào?",
            "  VD: 'Hiện tại đạt 23.2 điểm (HK2/11), cao hơn median (21.5) nhưng thấp hơn p75 (24.0),",
            "       xếp khoảng Top 35-50%. Điểm này CHỈ ĐỦ vào các trường khu vực (ĐH Đà Nẵng ~22),",
            "       CHƯA ĐỦ cho các trường top (ĐHBK Hà Nội ~25, ĐHQG HCM ~26).'",
            "",
            "CÂU 3-4: NGUYÊN NHÂN & ĐÁNH GIÁ",
            "  - Từ BARCHART: Môn nào là CHÂN KIỀNG? Môn nào KÉO LÙI?",
            "  - Chênh lệch giữa các môn? Ý nghĩa?",
            "  - Tiềm năng: Dễ cải thiện hay khó?",
            "  VD: 'Toán (8.5) và Lý (8.2) rất tốt, nhưng Hóa chỉ 6.5 - đây là ĐIỂM YẾU kéo tổng xuống.",
            "       Chênh 2.0 điểm giữa Toán-Hóa cho thấy NĂNG LỰC không đồng đều.",
            "       TIN TỐT: Hóa dễ cải thiện hơn Toán - nếu tăng Hóa lên 7.5 → tổng tăng 1.0 điểm!'",
            "",
            "## PHẦN 2: DỰ ĐOÁN TƯƠNG LAI & CHIẾN LƯỢC (4-5 câu)",
            "Từ LINECHART - Phân tích điểm dự đoán:",
            "",
            "CÂU 5: DỰ ĐOÁN & ĐÁNH GIÁ",
            "  - Nếu có type='future' trong linechart: Lấy điểm dự đoán",
            "  - So với hiện tại: Tăng/Giảm? Bao nhiêu điểm?",
            "  - Khả thi không? Dựa vào xu hướng quá khứ",
            "  VD: 'Dự đoán HK1/12 đạt 26.0 điểm (+2.8 so với hiện tại) - khá LẠC QUAN.",
            "       Tuy nhiên, dựa vào xu hướng tăng +0.5 điểm/kỳ trong quá khứ,",
            "       kịch bản THỰC TẾ hơn là 24.0-24.5 điểm nếu giữ nhịp độ.'",
            "",
            "CÂU 6: CƠ HỘI & KHUYẾN NGHỊ TRƯỜNG",
            "  - Với điểm dự đoán, đủ điều kiện trường nào?",
            "  - So với benchmark: Vượt p75? p90?",
            "  - Gợi ý trường phù hợp (từ KIẾN THỨC)",
            "  VD: 'Nếu đạt 26.0, vượt p90 (25.5) → Top 10%, ĐỦ ĐIỂM vào ĐHBK Hà Nội (~25),",
            "       ĐHQG HCM (~26), thậm chí xét thử ngành Cơ khí ĐHBK (~24.5).",
            "       Nhưng nếu chỉ đạt 24.0 → chỉ ở mức p75, CẦN DỰ PHÒNG với ĐH Bách Khoa Đà Nẵng (~23).'",
            "",
            "CÂU 7: LỘ TRÌNH CẢI THIỆN CỤ THỂ",
            "  - Từ BARCHART: Môn nào cần ưu tiên?",
            "  - Tăng bao nhiêu điểm ở môn nào để đạt mục tiêu?",
            "  - Phương pháp cụ thể (từ KIẾN THỨC)",
            "  VD: 'ƯU TIÊN TUYỆT ĐỐI: Hóa học (6.5 → 7.5 = +1.0 tổng).",
            "       Hành động: Ôn lại kiến thức lớp 11 (oxi hóa khử, cân bằng), làm 200 bài tập phản ứng,",
            "       học nhóm với bạn giỏi Hóa. KHÔNG LÀM NHIỀU Toán (đã 8.5) - tập trung vào điểm yếu!'",
            "",
            "CÂU 8: TÂM LÝ & ĐỘNG LỰC",
            "  - Đánh giá TIỀM NĂNG dựa vào quá khứ",
            "  - Khích lệ hoặc cảnh báo",
            "  - Lời khuyên tinh thần",
            "  VD: 'Xu hướng quá khứ (+2.3 trong 3 kỳ) chứng tỏ bạn CÓ KHẢ NĂNG và NGHỊ LỰC.",
            "       Điểm giảm ở HK2/11 là NHẤT THỜI - đừng nản! Nếu tiếp tục phương pháp học đúng,",
            "       26.0 điểm HOÀN TOÀN KHẢ THI. Hãy tin vào bản thân!'",
            "",
            "# QUY TẮC BẮT BUỘC:",
            "- CHỈ dùng số liệu từ linechart (field 'total') và barchart (field 'average')",
            "- PHẢI so sánh với benchmark (median, p75, p90)",
            "- PHẢI gợi ý trường cụ thể từ KIẾN THỨC",
            "- PHẢI phân tích CẢ quá khứ VÀ tương lai",
            "- Ngôn ngữ: Thân thiện, động viên, CỤ THỂ",
            "",
            "# YÊU CẦU TỔNG QUAN (headline):",
            "Tổng hợp 2-3 câu về:",
            "- Khối nào PHÙ HỢP NHẤT dựa vào điểm hiện tại + xu hướng?",
            "- Khối nào có TIỀM NĂNG cao nhất (dự đoán tốt)?",
            "- Khuyến nghị lựa chọn",
            "",
            "Định dạng: {\"headline\": \"...\", \"blocks\": [{\"id\": \"A00\", \"comment\": \"...\"}]}",
        ]

    def build_individual_subjects_instructions() -> List[str]:
        """Instructions for INDIVIDUAL SUBJECTS tab - analyzing each subject separately."""
        return [
            "Bạn là trợ lý học tập AI của EduTwin.",
            "Xưng hô: mình-bạn (mình là AI, bạn là học sinh).",
            "",
            "# NHIỆM VỤ: Phân tích TỪNG MÔN HỌC trong BỐI CẢNH TỔNG THỂ",
            "",
            "# DỮ LIỆU NHẬN ĐƯỢC:",
            "- subjects: Danh sách 9 môn (Toán, Văn, Anh, Lý, Hóa, Sinh, Sử, Địa, GDCD)",
            "- Mỗi môn có:",
            "  * average: Điểm TB tổng (từ HK1/10 đến hiện tại)",
            "  * chart_data với linechart: Xu hướng điểm qua các kỳ",
            "  * actual_examples: Ví dụ điểm thực tế",
            "  * future_examples: Ví dụ điểm dự đoán",
            "",
            "# CẤU TRÚC PHÂN TÍCH CHO MỖI MÔN (4-5 câu):",
            "",
            "1. VỊ TRÍ SO VỚI CÁC MÔN KHÁC:",
            "   - Dẫn đầu/Trung bình/Yếu nhất trong 9 môn?",
            "   - Điểm TB cụ thể là bao nhiêu?",
            "",
            "2. XU HƯỚNG:",
            "   - Tăng/Giảm/Ổn định qua các học kỳ?",
            "   - Tốc độ thay đổi?",
            "",
            "3. TIỀM NĂNG & DỰ ĐOÁN:",
            "   - Điểm dự đoán tương lai (nếu có)?",
            "   - So sánh tiềm năng với các môn khác?",
            "",
            "4. KHUYẾN NGHỊ:",
            "   - Nên tập trung cải thiện hay duy trì?",
            "   - Vai trò trong tổ hợp thi (A00/B00/C00/D01)?",
            "   - Hành động cụ thể?",
            "",
            "# QUY TẮC:",
            "- So sánh với 8 môn còn lại",
            "- Dùng SỐ LIỆU cụ thể từ dữ liệu",
            "- Mỗi môn 4-5 câu, ngắn gọn",
            "- Gắn với tổ hợp thi đại học",
            "",
            "# FORMAT RESPONSE - QUAN TRỌNG:",
            "BẮT BUỘC trả về JSON object theo format SAU, KHÔNG có markdown code block, KHÔNG có text giải thích thêm:",
            "",
            "{",
            '  "subjects": [',
            '    {"id": "Toan", "comment": "Toán đang dẫn đầu với 8.5 điểm - cao nhất trong 9 môn. Xu hướng tăng đều +0.3 điểm/kỳ, ổn định hơn các môn khác. Dự đoán HK1/12 đạt 9.0 - tiềm năng cao. Là môn chung của 4 tổ hợp, nên duy trì ở mức 8.5-9.0 và tập trung cải thiện môn yếu hơn."},',
            '    {"id": "Ngu van", "comment": "..."},',
            '    {"id": "Tieng Anh", "comment": "..."}',
            "  ]",
            "}",
            "",
            "CHỈ TRẢ VỀ JSON OBJECT, KHÔNG THÊM BẤT KỲ TEXT NÀO KHÁC!",
        ]
   
    

    # ==========================================
    # OPTIMIZED: Only analyze the active tab
    # ==========================================
    
    overview_response = {}
    exam_response = {}
    subject_response = {}
    
    # Determine which analysis to run based on active_tab
    if active_tab in ["Chung", "Khối TN", "Khối XH"]:
        # IMPROVED: Separate requests for each chart type to avoid confusion
        selected_tab_data = overview_chart_data.get(active_tab)
        if selected_tab_data:
            # Request 1: SUMMARY - Only linechart (current score) + benchmark
            summary_response = await ask_llm_for_chart(
                f"Tổng quan - {active_tab}",
                build_summary_instructions(),
                {
                    "meta": shared_meta,
                    "tab": active_tab,
                    "linechart": selected_tab_data["linechart"],
                    "current_term": selected_tab_data["current_term"],
                },
                {"summary": ""}
            )
            
            # Request 2: TREND - Only linechart (full timeline)
            trend_response = await ask_llm_for_chart(
                f"Xu hướng - {active_tab}",
                build_trend_instructions(),
                {
                    "meta": shared_meta,
                    "tab": active_tab,
                    "linechart": selected_tab_data["linechart"],
                },
                {"trend": ""}
            )
            
            # Request 3: SUBJECTS - Only barchart (subject averages)
            subjects_response = await ask_llm_for_chart(
                f"So sánh môn - {active_tab}",
                build_bars_instructions(),
                {
                    "meta": shared_meta,
                    "tab": active_tab,
                    "barchart": selected_tab_data["barchart"],
                },
                {"subjects": ""}
            )
            
            # Request 4: RADAR - Only radar (current term)
            radar_response = await ask_llm_for_chart(
                f"Phân bổ điểm - {active_tab}",
                build_radar_instructions(),
                {
                    "meta": shared_meta,
                    "tab": active_tab,
                    "radar": selected_tab_data["radar"],
                    "current_term": selected_tab_data["current_term"],
                },
                {"radar": ""}
            )
            
            # Combine results
            overview_response = {
                "tabs": [{
                    "id": active_tab,
                    "summary": summary_response.get("summary", ""),
                    "trend": trend_response.get("trend", ""),
                    "subjects": subjects_response.get("subjects", ""),
                    "radar": radar_response.get("radar", ""),
                }]
            }
    elif active_tab == "Tổ Hợp":
        # Analyze exam blocks
        exam_instructions = build_exam_blocks_instructions()
        exam_schema = {"headline": "", "blocks": [{"id": "", "comment": ""}]}
        exam_response = await ask_llm_for_group(
            "Đánh giá khối thi",
            exam_instructions,
            {"meta": shared_meta, **exam_blocks_payload},
            exam_schema,
        )
    elif active_tab == "Từng Môn":
        # Analyze individual subjects
        logger.info(f"[AI_ANALYSIS] Processing tab: Từng Môn, subjects count: {len(subject_payload)}")
        subject_instructions = build_individual_subjects_instructions()
        subject_schema = {"subjects": [{"id": "", "comment": ""}]}
        subject_response = await ask_llm_for_group(
            "Nhận xét từng môn",
            subject_instructions,
            {"meta": shared_meta, "subjects": subject_payload},
            subject_schema,
        )
        logger.info(f"[AI_ANALYSIS] Got subject_response with keys: {list(subject_response.keys()) if subject_response else 'empty'}")
    # Note: If active_tab is unknown, all responses remain empty (default behavior)

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
    
    # Persist to database if requested
    if payload.persist:
        try:
            # Save overview insights
            for tab_name in ["Chung", "Khối TN", "Khối XH"]:
                tab_data = overview_llm.get(tab_name, {})
                if tab_data.get("overview"):
                    insight = (
                        db.query(models.AIInsight)
                        .filter(
                            models.AIInsight.user_id == user_id,
                            models.AIInsight.insight_type == "slide_comment",
                            models.AIInsight.context_key == f"overview_{tab_name}"
                        )
                        .first()
                    )
                    if insight:
                        insight.content = tab_data["overview"]
                        insight.updated_at = datetime.utcnow()
                    else:
                        insight = models.AIInsight(
                            user_id=user_id,
                            insight_type="slide_comment",
                            context_key=f"overview_{tab_name}",
                            content=tab_data["overview"],
                            metadata_={"tab": tab_name, "version": 3}
                        )
                        db.add(insight)
            
            # Save exam block insights
            for block, block_data in exam_block_llm.items():
                if block_data.get("comment"):
                    insight = (
                        db.query(models.AIInsight)
                        .filter(
                            models.AIInsight.user_id == user_id,
                            models.AIInsight.insight_type == "slide_comment",
                            models.AIInsight.context_key == f"exam_block_{block}"
                        )
                        .first()
                    )
                    if insight:
                        insight.content = block_data["comment"]
                        insight.updated_at = datetime.utcnow()
                    else:
                        insight = models.AIInsight(
                            user_id=user_id,
                            insight_type="slide_comment",
                            context_key=f"exam_block_{block}",
                            content=block_data["comment"],
                            metadata_={"block": block, "version": 3}
                        )
                        db.add(insight)
            
            # Save subject insights
            for subject, subject_data in subject_llm.items():
                if subject_data.get("comment"):
                    insight = (
                        db.query(models.AIInsight)
                        .filter(
                            models.AIInsight.user_id == user_id,
                            models.AIInsight.insight_type == "slide_comment",
                            models.AIInsight.context_key == f"subject_{subject}"
                        )
                        .first()
                    )
                    if insight:
                        insight.content = subject_data["comment"]
                        insight.updated_at = datetime.utcnow()
                    else:
                        insight = models.AIInsight(
                            user_id=user_id,
                            insight_type="slide_comment",
                            context_key=f"subject_{subject}",
                            content=subject_data["comment"],
                            metadata_={"subject": subject, "version": 3}
                        )
                        db.add(insight)
            
            db.commit()
            logger.info(f"[AI_INSIGHTS] Persisted slide comments to database for user {user_id}")
        except Exception as e:
            logger.error(f"[AI_INSIGHTS] Failed to persist to database: {e}")
            db.rollback()
    
    return JSONResponse(content=resp)
