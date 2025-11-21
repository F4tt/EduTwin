from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Dict

from core.study_constants import GRADE_ORDER, SEMESTER_ORDER, SUBJECTS, SUBJECT_ALIASES


@dataclass
class ScoreUpdateIntent:
    subject: str
    new_score: float
    old_score: Optional[float]
    grade_level: Optional[str]
    semester: Optional[str]
    confidence: float
    raw_text: str


GRADE_PATTERN = re.compile(r"(?:lớp|khối)\s*(10|11|12|tn)", re.IGNORECASE)
SEMESTER_PATTERN = re.compile(r"(?:h[ôo]c k[ỳy]|hk)\s*(1|2|tn)", re.IGNORECASE)
SCORE_SPAN_PATTERN = re.compile(r"(?P<old>\d{1,2}(?:[.,]\d+)?)\s*(?:->|→|thành|lên|xuống)\s*(?P<new>\d{1,2}(?:[.,]\d+)?)")
SCORE_ONLY_PATTERN = re.compile(r"(?:điểm|score)[^\d]*(\d{1,2}(?:[.,]\d+)?)", re.IGNORECASE)


def _normalize_grade(found: Optional[str]) -> Optional[str]:
    if not found:
        return None
    value = found.upper()
    return "TN" if value == "TN" else value


def _normalize_semester(found: Optional[str]) -> Optional[str]:
    if not found:
        return None
    value = found.upper()
    return "TN" if value == "TN" else value


def _parse_score(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _find_subject(text: str) -> Optional[str]:
    for subject in SUBJECTS:
        if subject.lower() in text:
            return subject
    compact = re.sub(r"\s+|-", "", text.lower())
    for alias, subject in SUBJECT_ALIASES.items():
        if alias in compact:
            return subject
    return None


def detect_score_update_intent(message: str) -> Optional[ScoreUpdateIntent]:
    text_lower = message.lower()
    if "cập nhật" not in text_lower and "điểm" not in text_lower:
        return None

    subject = _find_subject(text_lower)
    if not subject:
        return None

    grade_match = GRADE_PATTERN.search(message)
    grade = _normalize_grade(grade_match.group(1) if grade_match else None)

    semester_match = SEMESTER_PATTERN.search(message)
    semester = _normalize_semester(semester_match.group(1) if semester_match else None)

    old_score: Optional[float] = None
    new_score: Optional[float] = None

    span_match = SCORE_SPAN_PATTERN.search(message)
    if span_match:
        old_score = _parse_score(span_match.group("old"))
        new_score = _parse_score(span_match.group("new"))
    else:
        score_match = SCORE_ONLY_PATTERN.search(message)
        if score_match:
            new_score = _parse_score(score_match.group(1))

    if new_score is None:
        return None

    confidence = 0.6
    if old_score is not None:
        confidence += 0.2
    if grade and grade in GRADE_ORDER:
        confidence += 0.1
    if grade and semester and semester in SEMESTER_ORDER.get(grade, []):
        confidence += 0.1

    confidence = min(confidence, 0.95)

    return ScoreUpdateIntent(
        subject=subject,
        new_score=new_score,
        old_score=old_score,
        grade_level=grade,
        semester=semester,
        confidence=confidence,
        raw_text=message,
    )


def detect_profile_update_intent(message: str) -> Optional[Dict[str, object]]:
    """Detect attempts to update profile fields like name, email, phone.

    Returns a dict: {field: 'email'|'phone'|'first_name'|'last_name', value: str, confidence: float}
    """
    text = message.strip()
    low = text.lower()

    # email
    m = re.search(r"([\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,})", message)
    if m:
        return {"field": "email", "value": m.group(1), "confidence": 0.95}

    # phone (basic VN phone pattern)
    m = re.search(r"(0\d{9}|\+?84\d{9})", message)
    if m:
        return {"field": "phone", "value": m.group(1), "confidence": 0.95}

    # name: looking for phrases like "tên tôi là X" or "mình tên là X"
    m = re.search(r"(?:tên tôi là|tôi tên là|mình tên là|mình tên là|tôi là)\s+([A-ZÀ-ỹa-zà-ỹ'\s]+)", message, flags=re.IGNORECASE)
    if m:
        # crude heuristic; take the first plausible name
        name = m.group(1).strip()
        # split into first/last if possible
        parts = name.split()
        if len(parts) >= 2:
            return {"field": "first_last", "value": name, "confidence": 0.7}
        if len(parts) == 1:
            return {"field": "first_name", "value": name, "confidence": 0.6}

    # fallback
    if "cập nhật" in low and ("email" in low or "gmail" in low or "số điện thoại" in low or "phone" in low or "họ" in low or "tên" in low):
        # low confidence, but indicates desire to update
        # try to extract common tokens
        if "email" in low or "gmail" in low:
            return {"field": "email", "value": None, "confidence": 0.6}
        if "số điện thoại" in low or "phone" in low:
            return {"field": "phone", "value": None, "confidence": 0.6}
        if "tên" in low or "họ" in low:
            return {"field": "first_last", "value": None, "confidence": 0.6}
    return None


def detect_personalization_intent(message: str) -> Optional[Dict[str, object]]:
    """Detect non-sensitive personalization like salutation, tone, favorites.

    Returns: {field: str, value: Any, confidence: float}
    """
    low = message.lower()

    # salutation / how to address
    m = re.search(r"(gọi tôi là|xưng tôi là|xưng hô là|gọi tôi bằng)\s*[:\-\s]*([A-Za-zÀ-ỹ0-9\s]+)", message, flags=re.IGNORECASE)
    if m:
        val = m.group(2).strip()
        if val:
            return {"field": "salutation", "value": val, "confidence": 0.9}

    # tone / style
    if any(k in low for k in ("ngôn ngữ chính thức", "formal", "trang trọng", "thân mật", "informal", "thân thiện")):
        if "formal" in low or "trang trọng" in low:
            return {"field": "tone", "value": "formal", "confidence": 0.8}
        if "informal" in low or "thân mật" in low or "thân thiện" in low:
            return {"field": "tone", "value": "informal", "confidence": 0.8}

    # likes/interests (simple heuristic)
    m = re.search(r"(thích|tôi thích|mình thích)\s+([A-Za-zÀ-ỹ0-9\s,]+)", message, flags=re.IGNORECASE)
    if m:
        val = m.group(2).strip()
        return {"field": "interests", "value": [v.strip() for v in re.split(r",|và|and", val) if v.strip()], "confidence": 0.7}

    # small talk like preferred summary length or detail
    if any(k in low for k in ("ngắn gọn", "chi tiết", "ít chữ", "nhiều chi tiết")):
        if "ngắn" in low or "ít chữ" in low:
            return {"field": "detail_level", "value": "short", "confidence": 0.8}
        if "chi tiết" in low or "nhiều chi tiết" in low:
            return {"field": "detail_level", "value": "detailed", "confidence": 0.8}

    return None

