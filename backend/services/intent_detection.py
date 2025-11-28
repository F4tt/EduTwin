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


def detect_confirmation_intent(message: str) -> bool:
    """
    Detect if user is confirming a previous suggestion/request.
    Returns True if message contains confirmation keywords.
    """
    text_lower = message.lower().strip()
    
    confirmation_keywords = [
        "xác nhận",
        "confirm",
        "đồng ý",
        "ok",
        "okay",
        "được",
        "chấp nhận",
        "yes",
        "có",
        "ừ",
        "oke",
        "đúng",
        "cập nhật đi",
        "thay đổi đi",
        "làm đi",
        "thực hiện",
        "chính xác"
    ]
    
    # Check if message is short (< 10 words) and contains confirmation keywords
    word_count = len(text_lower.split())
    if word_count <= 10:
        for keyword in confirmation_keywords:
            if keyword in text_lower:
                return True
    
    return False


def detect_cancellation_intent(message: str) -> bool:
    """
    Detect if user is canceling a previous suggestion/request.
    Returns True if message contains cancellation keywords.
    """
    text_lower = message.lower().strip()
    
    cancellation_keywords = [
        "không",
        "no",
        "cancel",
        "huỷ",
        "hủy",
        "thôi",
        "bỏ",
        "từ chối",
        "không đồng ý"
    ]
    
    word_count = len(text_lower.split())
    if word_count <= 10:
        for keyword in cancellation_keywords:
            if keyword in text_lower:
                return True
    
    return False


GRADE_PATTERN = re.compile(
    r"(?:lớp|khối|lop|khoi)\s+"
    r"(10|11|12|tn|mười\s+hai|muoi\s+hai|mười\s+một|muoi\s+mot|mười|muoi)",
    re.IGNORECASE
)
SEMESTER_PATTERN = re.compile(
    r"(?:h[ôọoóòỏõọ]c\s*k[ỳýỵỷỹy]|hk|hoc\s*ky)\s+"
    r"(1|2|tn|một|mot|hai)",
    re.IGNORECASE
)
SCORE_SPAN_PATTERN = re.compile(
    r"(?P<old>\d{1,2}(?:[.,]\d+)?)\s*"
    r"(?:->|→|thành|thanh|lên|len|xuống|xuong|sang)\s*"
    r"(?P<new>\d{1,2}(?:[.,]\d+)?)"
)
# Priority patterns for score extraction (more specific → less specific)
SCORE_EXPLICIT_PATTERN = re.compile(
    r"(?:là|la|thành|thanh|bằng|bang|được|duoc|dc)\s*"
    r"(\d{1,2}(?:[.,]\d+)?)",
    re.IGNORECASE
)
SCORE_ONLY_PATTERN = re.compile(
    r"(?:điểm|diem|score)\s*(?:số|so)?\s*"
    r"(\d{1,2}(?:[.,]\d+)?)",
    re.IGNORECASE
)


def _normalize_number_text(text: str) -> Optional[str]:
    """Convert Vietnamese number words to digits."""
    text_lower = text.lower().strip()
    
    # Map Vietnamese numbers to digits
    number_map = {
        'một': '1',
        'mot': '1',
        'hai': '2',
        'ba': '3',
        'bốn': '4',
        'bon': '4',
        'tư': '4',
        'tu': '4',
        'năm': '5',
        'nam': '5',
        'sáu': '6',
        'sau': '6',
        'bảy': '7',
        'bay': '7',
        'tám': '8',
        'tam': '8',
        'chín': '9',
        'chin': '9',
        'mười': '10',
        'muoi': '10',
        'muời': '10',
        'mười một': '11',
        'muoi mot': '11',
        'muoi một': '11',
        'mười hai': '12',
        'muoi hai': '12',
        'muoi hai': '12',
        'mươi một': '11',
        'muoi mot': '11',
        'mươi hai': '12',
        'muoi hai': '12',
    }
    
    return number_map.get(text_lower)


def _normalize_grade(found: Optional[str]) -> Optional[str]:
    """Normalize grade value, converting text to numbers."""
    if not found:
        return None
    
    # Try converting text to number first
    num = _normalize_number_text(found)
    if num:
        return num
    
    value = found.upper()
    return "TN" if value == "TN" else value


def _normalize_semester(found: Optional[str]) -> Optional[str]:
    """Normalize semester value, converting text to numbers."""
    if not found:
        return None
    
    # Try converting text to number first
    num = _normalize_number_text(found)
    if num:
        return num
    
    value = found.upper()
    return "TN" if value == "TN" else value


def _parse_score(text: str) -> Optional[float]:
    try:
        return float(text.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _normalize_vietnamese(text: str) -> str:
    """Remove Vietnamese accents for matching."""
    replacements = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
        'đ': 'd',
    }
    result = text.lower()
    for vn_char, latin in replacements.items():
        result = result.replace(vn_char, latin)
    return result


def _find_subject(text: str) -> Optional[str]:
    """Find subject from text, handling both accented and non-accented Vietnamese."""
    text_normalized = _normalize_vietnamese(text)
    
    # Try exact match first (for non-accented)
    for subject in SUBJECTS:
        if subject.lower() in text:
            return subject
    
    # Try with normalized (remove accents)
    for subject in SUBJECTS:
        if subject.lower() in text_normalized:
            return subject
    
    # Try aliases
    compact = re.sub(r"\s+|-", "", text.lower())
    for alias, subject in SUBJECT_ALIASES.items():
        if alias in compact:
            return subject
    
    # Try aliases with normalized
    compact_normalized = re.sub(r"\s+|-", "", text_normalized)
    for alias, subject in SUBJECT_ALIASES.items():
        if alias in compact_normalized:
            return subject
    
    return None


def detect_score_update_intent(message: str) -> Optional[ScoreUpdateIntent]:
    """
    Detect score update intent with comprehensive support for:
    - Numbers as text (một, hai, mười, etc.)
    - With/without Vietnamese accents
    - Common typos (thanh → thành, duoc → được)
    - Flexible patterns
    """
    text_lower = message.lower()
    
    # Normalize text for better matching (remove accents)
    text_normalized = _normalize_vietnamese(text_lower)
    
    # Expanded keyword list for score updates
    update_keywords = [
        "cập nhật", "cap nhat", "capnhat",
        "điểm", "diem", "điem",
        "update", "thay đổi", "thay doi", "thaydoi",
        "sửa", "sua", "chỉnh", "chinh",
        "nhập", "nhap"
    ]
    
    has_update_keyword = any(kw in text_normalized for kw in update_keywords)
    
    if not has_update_keyword:
        return None

    subject = _find_subject(text_lower)
    
    # If no subject found, return None
    # (chatbot will ask for clarification)
    if not subject:
        return None

    # Extract grade (support both numbers and text: 10, mười, muoi)
    grade_match = GRADE_PATTERN.search(message)
    grade = _normalize_grade(grade_match.group(1) if grade_match else None)

    # Extract semester (support both numbers and text: 1, một, mot)
    semester_match = SEMESTER_PATTERN.search(message)
    semester = _normalize_semester(semester_match.group(1) if semester_match else None)

    old_score: Optional[float] = None
    new_score: Optional[float] = None

    # Priority 1: Span pattern (9 -> 7, 9 thành 7, 9 → 7.5)
    span_match = SCORE_SPAN_PATTERN.search(message)
    if span_match:
        old_score = _parse_score(span_match.group("old"))
        new_score = _parse_score(span_match.group("new"))
    else:
        # Priority 2: Explicit score keywords (là 7, thành 7, được 8.5, dc 9)
        explicit_match = SCORE_EXPLICIT_PATTERN.search(message)
        if explicit_match:
            new_score = _parse_score(explicit_match.group(1))
        else:
            # Priority 3: Score after "điểm" (điểm 7, điểm số 8, diem 9)
            score_match = SCORE_ONLY_PATTERN.search(message)
            if score_match:
                new_score = _parse_score(score_match.group(1))

    if new_score is None:
        return None

    # Validate score range (0-10)
    if new_score < 0 or new_score > 10:
        return None

    # Calculate confidence based on available information
    confidence = 0.5  # Base confidence
    
    if old_score is not None:
        confidence += 0.2  # Has old score (more specific)
    if grade and grade in GRADE_ORDER:
        confidence += 0.1  # Valid grade
    if semester and grade and semester in SEMESTER_ORDER.get(grade, []):
        confidence += 0.15  # Valid semester for grade
    if subject:
        confidence += 0.1  # Has subject

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

