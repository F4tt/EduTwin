from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import models, database
from utils.session_utils import require_auth, get_current_user

router = APIRouter(prefix="/study", tags=["Study"])

SUBJECTS = [
    "Toán",
    "Ngữ văn",
    "Vật lý",
    "Hóa học",
    "Sinh học",
    "Lịch sử",
    "Địa lý",
    "Tiếng Anh",
    "Giáo dục công dân",
]

GRADE_ORDER = ["10", "11", "12", "TN"]
SEMESTER_ORDER: Dict[str, List[str]] = {
    "10": ["1", "2"],
    "11": ["1", "2"],
    "12": ["1", "2"],
    "TN": ["TN"],
}
GRADE_DISPLAY = {
    "10": "Lớp 10",
    "11": "Lớp 11",
    "12": "Lớp 12",
    "TN": "Tốt nghiệp",
}
SEMESTER_DISPLAY = {"1": "Học kỳ 1", "2": "Học kỳ 2", "TN": "Kỳ thi tốt nghiệp"}


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


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    }


@router.post("/scores/bulk")
@require_auth
def upsert_scores(request: Request, payload: ScoreBulkPayload, db: Session = Depends(get_db)):
    user_session = get_current_user(request)
    if not user_session:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    user_id = user_session.get("user_id")
    updates = 0

    for record in payload.scores:
        grade = record.grade_level
        semester = record.semester
        subject = record.subject
        validate_combination(grade, semester, subject)

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
        score_entry.actual_updated_at = datetime.utcnow()
        updates += 1

    db.commit()

    return {"updated": updates}
