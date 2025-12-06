from __future__ import annotations

from typing import Optional, Tuple

from core.study_constants import GRADE_ORDER, SEMESTER_ORDER, SUBJECTS, SUBJECT_ALIASES

FEATURE_KEY_DELIM = "|"


def _clean_token(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("đ", "d")
    )


def normalize_subject_token(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text in SUBJECTS:
        return text
    compact = _clean_token(text)
    return SUBJECT_ALIASES.get(compact)


def normalize_grade_token(value: object) -> Optional[str]:
    if value is None:
        return None
    grade = str(value).strip().upper()
    return grade if grade in GRADE_ORDER else None


def normalize_semester_token(grade: Optional[str], value: object) -> Optional[str]:
    if value is None:
        return None
    semester = str(value).strip().upper()
    if not grade:
        return semester
    if grade in SEMESTER_ORDER and semester in SEMESTER_ORDER[grade]:
        return semester
    return None


def parse_compound_header(header: object) -> Optional[Tuple[str, str, str]]:
    if header is None:
        return None
    text = str(header).strip()
    if not text:
        return None
    tokens = [tok for tok in text.replace("-", "_").split("_") if tok]
    if not tokens:
        return None

    subject = normalize_subject_token(tokens[0])
    if not subject:
        return None

    if len(tokens) == 3:
        semester_token = tokens[1]
        grade_token = tokens[2]
    else:
        return None

    grade = normalize_grade_token(grade_token)
    if not grade:
        return None

    semester = normalize_semester_token(grade, semester_token)
    if not semester:
        return None

    return subject, semester, grade


def build_feature_key(subject: str, semester: str, grade: str) -> str:
    return f"{subject}{FEATURE_KEY_DELIM}{semester}{FEATURE_KEY_DELIM}{grade}"


def split_feature_key(key: str) -> Tuple[str, str, str]:
    parts = key.split(FEATURE_KEY_DELIM)
    if len(parts) != 3:
        raise ValueError(f"Invalid feature key: {key}")
    return parts[0], parts[1], parts[2]

