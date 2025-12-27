from __future__ import annotations

import os
from typing import Dict, List, Optional

from services.llm_provider import get_llm_provider
import httpx
from sqlalchemy.orm import Session
import re

from db import models
from services.pii_redaction import redact_message_content, prepare_safe_llm_prompt, redact_user_for_llm
# NOTE: educational_knowledge removed - now using Custom Structure documents for context


# ========== Intent Detection Classes ==========

class ScoreUpdateIntent:
    """Represents a detected score update intent from user message."""
    def __init__(self, subject: str, new_score: float, old_score: Optional[float] = None, confidence: float = 0.0):
        self.subject = subject
        self.new_score = new_score
        self.old_score = old_score
        self.confidence = confidence


def detect_personalization_intent(message: str) -> Optional[Dict[str, object]]:
    """
    Detect personalization intent from user message using keyword matching.
    Returns dict with 'field', 'value', 'confidence' if detected, else None.
    
    Detects patterns like:
    - "Tôi thích học môn Toán" -> {field: 'favorite_subject', value: 'Toán', confidence: 0.8}
    - "Tôi là học sinh lớp 12" -> {field: 'grade', value: '12', confidence: 0.9}
    - "Tôi muốn học vào buổi tối" -> {field: 'study_time', value: 'evening', confidence: 0.7}
    """
    if not message:
        return None
    
    message_lower = message.lower()
    
    # Detect grade level
    grade_patterns = [
        (r'lớp\s*(\d+)', 'grade'),
        (r'khối\s*(\d+)', 'grade'),
    ]
    for pattern, field in grade_patterns:
        match = re.search(pattern, message_lower)
        if match:
            return {'field': field, 'value': match.group(1), 'confidence': 0.9}
    
    # Detect favorite subject
    subjects = ['toán', 'văn', 'anh', 'lý', 'hóa', 'sinh', 'sử', 'địa', 'gdcd', 'tin']
    for subj in subjects:
        if f'thích {subj}' in message_lower or f'thích môn {subj}' in message_lower:
            return {'field': 'favorite_subject', 'value': subj.capitalize(), 'confidence': 0.8}
    
    # Detect study time preference
    if 'buổi sáng' in message_lower or 'sáng sớm' in message_lower:
        return {'field': 'study_time', 'value': 'morning', 'confidence': 0.7}
    if 'buổi tối' in message_lower or 'tối' in message_lower:
        return {'field': 'study_time', 'value': 'evening', 'confidence': 0.7}
    if 'buổi chiều' in message_lower:
        return {'field': 'study_time', 'value': 'afternoon', 'confidence': 0.7}
    
    return None


def set_user_preference(db: Session, user_id: int, key: str, value) -> dict:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {}
    prefs = user.preferences or {}
    prefs[key] = value
    user.preferences = prefs
    db.commit()
    return prefs


def build_user_summary(user) -> str:
    if not user:
        return ""
    parts = []
    if user.first_name or user.last_name:
        parts.append(f"Tên: {user.first_name or ''} {user.last_name or ''}".strip())
    if user.current_grade:
        parts.append(f"Khối: {user.current_grade}")
    prefs = user.preferences or {}
    if prefs:
        parts.append("Sở thích: " + ", ".join(f"{k}={v}" for k, v in prefs.items()))
    return "; ".join(parts)


# Token counting utilities
def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 characters for Vietnamese/English mix"""
    return len(text) // 4


def truncate_text(text: str, max_tokens: int = 500) -> str:
    """Truncate text to approximate token limit"""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[đã rút gọn]"


def extract_relevant_sections(document_content: str, keywords: List[str], max_tokens: int = 300) -> str:
    """Extract sections from document that contain keywords"""
    if not document_content or not keywords:
        return truncate_text(document_content or "", max_tokens)
    
    # Split into paragraphs
    paragraphs = [p.strip() for p in document_content.split('\n\n') if p.strip()]
    if not paragraphs:
        paragraphs = [document_content]
    
    # Score paragraphs by keyword matches
    scored = []
    for para in paragraphs:
        para_lower = para.lower()
        score = sum(1 for kw in keywords if kw.lower() in para_lower)
        if score > 0:
            scored.append((score, para))
    
    # Sort by score and take top sections
    scored.sort(reverse=True, key=lambda x: x[0])
    result_parts = [para for _, para in scored[:3]]  # Top 3 relevant paragraphs
    
    result = '\n\n'.join(result_parts) if result_parts else paragraphs[0] if paragraphs else ""
    return truncate_text(result, max_tokens)


LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))


async def _call_remote_llm(messages: List[Dict[str, str]], temperature: float = 0.2) -> Optional[str]:
    provider = get_llm_provider()
    resp = await provider.chat(messages=messages, temperature=temperature)
    if not resp:
        return None

    # tolerant extraction: try several known response shapes (OpenAI-style, Google-style, generic)
    def _extract_text(resp: dict) -> Optional[str]:
        # Official Google Generative AI API response format
        # See: https://ai.google.dev/api/rest/v1beta/models/generateContent
        candidates = resp.get("candidates")
        if isinstance(candidates, list) and candidates:
            cand0 = candidates[0]
            if isinstance(cand0, dict):
                content = cand0.get("content")
                if isinstance(content, dict):
                    parts = content.get("parts")
                    if isinstance(parts, list) and parts:
                        part0 = parts[0]
                        if isinstance(part0, dict) and isinstance(part0.get("text"), str):
                            return part0.get("text")

        # OpenAI Chat completion shape
        choices = resp.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                # ChatCompletions
                msg = first.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg.get("content")
                # choices[].text (older completions)
                if isinstance(first.get("text"), str):
                    return first.get("text")

        # Google/Vertex AI style (legacy)
        outputs = resp.get("outputs")
        if isinstance(outputs, list) and outputs:
            out0 = outputs[0]
            # outputs[0].content could be list of dicts
            content = out0.get("content")
            if isinstance(content, list) and content:
                firstc = content[0]
                if isinstance(firstc, dict) and isinstance(firstc.get("text"), str):
                    return firstc.get("text")
            if isinstance(out0.get("text"), str):
                return out0.get("text")

        # Some APIs return predictions or candidates
        preds = resp.get("predictions")
        if isinstance(preds, list) and preds:
            p0 = preds[0]
            if isinstance(p0, dict):
                if isinstance(p0.get("content"), str):
                    return p0.get("content")
                if isinstance(p0.get("text"), str):
                    return p0.get("text")

        # fallback: scan for first reasonable string in nested structure
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

        return _scan(resp)

    return _extract_text(resp)


def _extract_subject_keywords(message: str) -> List[str]:
    """Extract subject names mentioned in message for targeted score filtering"""
    subject_map = {
        'toán': 'Toán',
        'lý': 'Vật Lý', 'vật lý': 'Vật Lý', 'ly': 'Vật Lý',
        'hóa': 'Hóa Học', 'hoa': 'Hóa Học',
        'văn': 'Ngữ Văn', 'van': 'Ngữ Văn',
        'anh': 'Tiếng Anh', 'tiếng anh': 'Tiếng Anh',
        'sinh': 'Sinh Học',
        'sử': 'Lịch Sử', 'su': 'Lịch Sử', 'lịch sử': 'Lịch Sử',
        'địa': 'Địa Lý', 'dia': 'Địa Lý', 'địa lý': 'Địa Lý',
        'gdcd': 'GDCD', 'công dân': 'GDCD'
    }
    
    message_lower = message.lower()
    found_subjects = []
    for keyword, subject_name in subject_map.items():
        if keyword in message_lower:
            found_subjects.append(subject_name)
    
    return list(set(found_subjects))  # Remove duplicates


def _get_dataset_summary(db: Session, structure_id: int, user_scores: Optional[Dict[str, float]] = None) -> str:
    """
    Get aggregated dataset statistics (cached).
    Returns only summary stats (avg, percentiles) NOT raw data to save tokens.
    """
    try:
        # Check if dataset exists - using CustomDatasetSample (the current model)
        samples = db.query(models.CustomDatasetSample).filter(
            models.CustomDatasetSample.structure_id == structure_id
        ).limit(100).all()  # Limit for performance
        
        if not samples:
            return ""
        
        # Calculate aggregated stats from score_data JSON
        all_scores = []
        for sample in samples:
            if sample.score_data and isinstance(sample.score_data, dict):
                scores = [v for v in sample.score_data.values() if isinstance(v, (int, float)) and 0 <= v <= 10000]
                if scores:
                    all_scores.extend(scores)
        
        if not all_scores:
            return ""
        
        all_scores.sort()
        n = len(all_scores)
        avg = sum(all_scores) / n
        median = all_scores[n // 2]
        p75 = all_scores[int(n * 0.75)]
        p90 = all_scores[int(n * 0.90)]
        
        summary = f"📊 Dataset: TB={avg:.1f}, Trung vị={median:.1f}, Top 25%≥{p75:.1f}, Top 10%≥{p90:.1f}"
        
        # Add user comparison if scores provided
        if user_scores:
            user_avg = sum(user_scores.values()) / len(user_scores) if user_scores else 0
            # Inline percentile calculation
            all_averages = []
            for sample in samples:
                if sample.score_data and isinstance(sample.score_data, dict):
                    scores = [v for v in sample.score_data.values() if isinstance(v, (int, float)) and 0 <= v <= 10000]
                    if scores:
                        all_averages.append(sum(scores) / len(scores))
            if all_averages:
                all_averages.sort()
                percentile = sum(1 for avg_val in all_averages if avg_val < user_avg) / len(all_averages) * 100
                summary += f" | Bạn: TB={user_avg:.1f} (top {100-percentile:.0f}%)"
        
        return summary
        
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Dataset summary error: {e}")
        return ""


def _build_context_blocks(user_id: Optional[int], message: str, db: Optional[Session] = None) -> List[Dict[str, object]]:
    """
    Build context blocks using simple SQL queries instead of vector search.
    Optimized for token efficiency:
    - Only includes relevant scores (filtered by subject keywords)
    - Truncates chat history to last 3 messages
    - Returns summarized format
    """
    contexts: List[Dict[str, object]] = []
    
    if user_id is None or db is None:
        return contexts
    
    # Get recent chat messages for context (last 3 to save tokens)
    recent_messages = db.query(models.ChatMessage)\
        .join(models.ChatSession, models.ChatMessage.session_id == models.ChatSession.id)\
        .filter(models.ChatSession.user_id == user_id)\
        .order_by(models.ChatMessage.created_at.desc())\
        .limit(5)\
        .all()
    
    # Compress chat history into single context block
    if recent_messages:
        chat_summary = []
        for msg in reversed(recent_messages):
            prefix = "U" if msg.role == 'user' else "A"
            # Truncate long messages
            content = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
            chat_summary.append(f"{prefix}: {content}")
        
        contexts.append({
            "title": "Hội thoại gần đây",
            "content": "\n".join(chat_summary),
            "score": 1.0,
            "metadata": {"type": "chat_history"}
        })
    
    # Get scores only if message mentions subjects/grades
    score_keywords = ['điểm', 'toán', 'lý', 'hóa', 'văn', 'anh', 'sinh', 'sử', 'địa', 'gdcd', 'học kỳ', 'lớp', 'kết quả', 'thành tích', 'thi', 'kiểm tra', 'dự đoán']
    if any(kw in message.lower() for kw in score_keywords):
        # Get active structure
        active_structure = db.query(models.CustomTeachingStructure).filter(
            models.CustomTeachingStructure.is_active == True
        ).first()
        
        if active_structure:
            # Get user's current time point preference
            user_pref = db.query(models.UserStructurePreference).filter(
                models.UserStructurePreference.user_id == user_id,
                models.UserStructurePreference.structure_id == active_structure.id
            ).first()
            
            current_tp = user_pref.current_timepoint if user_pref and user_pref.current_timepoint else None
            time_point_labels = active_structure.time_point_labels or []
            
            # Determine current time point index
            if current_tp and current_tp in time_point_labels:
                current_tp_index = time_point_labels.index(current_tp)
            else:
                # Default to last time point with actual data
                current_tp_index = 0
            
            # Get ALL scores for this user+structure (both actual and predicted)
            all_scores = db.query(models.CustomUserScore).filter(
                models.CustomUserScore.user_id == user_id,
                models.CustomUserScore.structure_id == active_structure.id
            ).all()
            
            # Categorize scores by temporal status
            past_scores = []      # time_point_index < current_tp_index
            current_scores = []   # time_point_index == current_tp_index
            future_scores = []    # time_point_index > current_tp_index
            
            for score in all_scores:
                # Get time point index
                if score.time_point in time_point_labels:
                    tp_index = time_point_labels.index(score.time_point)
                else:
                    continue
                
                # Determine score type
                if score.actual_score is not None:
                    score_value = score.actual_score
                    score_type = "thực tế"
                    marker = "✓"
                elif score.predicted_score is not None:
                    score_value = score.predicted_score
                    score_type = "dự đoán"
                    marker = "⚡"
                else:
                    continue  # No data
                
                score_info = {
                    "subject": score.subject,
                    "time_point": score.time_point,
                    "value": score_value,
                    "type": score_type,
                    "marker": marker,
                    "source": score.predicted_source if score.actual_score is None else None
                }
                
                # Categorize by temporal status
                if tp_index < current_tp_index:
                    past_scores.append(score_info)
                elif tp_index == current_tp_index:
                    current_scores.append(score_info)
                else:
                    future_scores.append(score_info)
            
            # Build enhanced context string
            context_parts = []
            context_parts.append(f"📊 ĐIỂM SỐ (Cấu trúc: \"{active_structure.structure_name}\", Thời điểm hiện tại: {current_tp or 'chưa xác định'})")
            
            # Format past scores
            if past_scores:
                past_lines = []
                subjects = {}
                for s in past_scores:
                    if s["subject"] not in subjects:
                        subjects[s["subject"]] = []
                    subjects[s["subject"]].append(f"{s['time_point']}={s['value']}{s['marker']}")
                for subj, scores in subjects.items():
                    past_lines.append(f"  • {subj}: {', '.join(scores)}")
                context_parts.append("🔙 QUÁ KHỨ:")
                context_parts.extend(past_lines)  # No limit - include all subjects
            
            # Format current scores
            if current_scores:
                curr_lines = []
                for s in current_scores:
                    status = f"({s['type']})" if s['type'] == 'dự đoán' else ""
                    curr_lines.append(f"  • {s['subject']}: {s['value']}{s['marker']} {status}")
                context_parts.append("📍 HIỆN TẠI:")
                context_parts.extend(curr_lines)  # No limit - include all subjects
            
            # Format future predictions
            if future_scores:
                fut_lines = []
                subjects = {}
                for s in future_scores:
                    if s["subject"] not in subjects:
                        subjects[s["subject"]] = []
                    subjects[s["subject"]].append(f"{s['time_point']}={s['value']}{s['marker']}")
                for subj, scores in subjects.items():
                    fut_lines.append(f"  • {subj}: {', '.join(scores)}")
                context_parts.append("TƯƠNG LAI (dự đoán):")
                context_parts.extend(fut_lines)  # No limit - include all subjects
            
            # Add legend
            if past_scores or current_scores or future_scores:
                context_parts.append("Chú thích: ✓=thực tế, ⚡=dự đoán ML")
            
            # Create context block
            if len(context_parts) > 1:  # Has more than just header
                contexts.append({
                    "title": "Điểm số học sinh",
                    "content": "\n".join(context_parts),
                    "score": 0.95,
                    "metadata": {
                        "type": "enhanced_score_data",
                        "structure": active_structure.structure_name,
                        "current_timepoint": current_tp,
                        "past_count": len(past_scores),
                        "current_count": len(current_scores),
                        "future_count": len(future_scores)
                    }
                })
    
    return contexts

def _build_prompt(
    message: str, 
    contexts: List[Dict[str, object]], 
    user_profile: Optional[Dict[str, object]], 
    db: Optional[Session] = None, 
    user_id: Optional[int] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> List[Dict[str, str]]:
    """Build optimized system prompt with dynamic context selection and custom structure adaptation."""
    
    # NOTE: Legacy educational_knowledge.get_educational_context() removed
    # Context is now dynamically loaded from CustomStructureDocument associated with active structure
    
    # Base instructions (always included, lightweight)
    instructions = (
        "Bạn là trợ lý học tập thông minh của nền tảng EduTwin. "
        "Luôn phản hồi bằng tiếng Việt, ngắn gọn, thân thiện và tập trung vào việc hỗ trợ học tập. "
        "Nếu có dữ liệu điểm số hoặc thông tin cá nhân liên quan, hãy ưu tiên sử dụng để cá nhân hóa câu trả lời. "
        "Nếu cần cập nhật dữ liệu, hãy yêu cầu xác nhận rõ ràng.\n\n"
        "⚠️ LƯU Ý BẢO MẬT: Thông tin người dùng đã được ẩn danh hóa để bảo vệ quyền riêng tư."
    )
    
    # ADAPTIVE PROMPTING: Inject custom structure context if active
    custom_structure_info = ""
    if db:
        try:
            active_structure = db.query(models.CustomTeachingStructure).filter(
                models.CustomTeachingStructure.is_active == True
            ).first()
            
            if active_structure:
                # Build structure-aware context
                subjects_str = ", ".join(active_structure.subject_labels)  # No limit - include all
                time_points_str = ", ".join(active_structure.time_point_labels)  # No limit - include all
                
                custom_structure_info = (
                    f"\n\n📚 HỆ THỐNG ĐÁNH GIÁ HIỆN TẠI:\n"
                    f"- Tên: {active_structure.structure_name}\n"
                    f"- Thang điểm: {active_structure.scale_type}\n"
                    f"- Môn học ({active_structure.num_subjects}): {subjects_str}\n"
                    f"- Thời điểm ({active_structure.num_time_points}): {time_points_str}\n"
                )
                
                # Add structure documents if available (with smart extraction)
                structure_docs = db.query(models.CustomStructureDocument).filter(
                    models.CustomStructureDocument.structure_id == active_structure.id
                ).limit(6).all()  # Get up to 6 docs but filter by relevance
                
                if structure_docs:
                    # Extract keywords from user message for document filtering
                    message_keywords = _extract_subject_keywords(message)
                    if not message_keywords:
                        # Use general keywords if no subject mentioned
                        message_keywords = message.lower().split()[:5]  # First 5 words
                    
                    custom_structure_info += "\n📄 TÀI LIỆU THAM KHẢO:\n"
                    docs_included = 0
                    for doc in structure_docs:
                        if docs_included >= 5:  # Limit to 5 most relevant docs
                            break
                        
                        # Use extracted_summary (optimized) instead of full content
                        if doc.extracted_summary:
                            # Extract relevant sections based on keywords
                            relevant_text = extract_relevant_sections(
                                doc.extracted_summary, 
                                message_keywords, 
                                max_tokens=300
                            )
                            if relevant_text and relevant_text != "...[đã rút gọn]":
                                custom_structure_info += f"- {doc.file_name}: {relevant_text}\n"
                                docs_included += 1
                
                # Add dataset benchmark summary (only if comparing scores)
                benchmark_keywords = ['so sánh', 'xếp hạng', 'top', 'trung bình', 'giỏi', 'yếu', 'khá', 'dataset', 'benchmark']
                if any(kw in message.lower() for kw in benchmark_keywords) and user_id:
                    # Get user's current scores for comparison
                    user_score_records = db.query(models.CustomUserScore).filter(
                        models.CustomUserScore.user_id == user_id,
                        models.CustomUserScore.structure_id == active_structure.id,
                        models.CustomUserScore.actual_score.isnot(None)
                    ).all()
                    
                    if user_score_records:
                        user_scores_dict = {s.subject: s.actual_score for s in user_score_records}
                        dataset_summary = _get_dataset_summary(db, active_structure.id, user_scores_dict)
                        if dataset_summary:
                            custom_structure_info += f"\n{dataset_summary}\n"
                
                instructions += custom_structure_info
        except Exception as e:
            # Log but don't fail - fallback to default prompt
            import logging
            logging.getLogger("uvicorn.error").warning(f"Failed to load custom structure context: {e}")
    
    # build context block
    context_texts = []
    for idx, ctx in enumerate(contexts, start=1):
        title = ctx.get("title") or f"Thông tin #{idx}"
        content = ctx.get("content", "")
        context_texts.append(f"{idx}. {title}\n{content}")

    context_block = "\n\n".join(context_texts) if context_texts else ""

    # user profile block - REDACT PII before sending to LLM
    profile_block = ""
    if user_profile:
        # Redact PII from user profile
        safe_profile = redact_user_for_llm(user_profile)
        profile_pairs = [f"{key}: {value}" for key, value in safe_profile.items() if value]
        if profile_pairs:
            profile_block = "Thông tin người dùng (đã ẩn danh):\n" + "\n".join(profile_pairs)

    system_msg = instructions
    if profile_block:
        system_msg = f"{system_msg}\n\n{profile_block}"

    # return system-level content and a separate system message for RAG contexts (if any)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_msg}]
    if context_block:
        messages.append({"role": "system", "content": f"Dữ liệu liên quan:\n{context_block}"})

    # the calling code will append prior conversation and the current user message
    return messages


def _build_chart_prompt(
    chart_data: Dict[str, object],
    chart_type: str,
    user_id: int,
    db: Session
) -> List[Dict[str, str]]:
    """
    Build optimized prompt specifically for chart analysis.
    Only includes:
    - Scores visible in the chart (not all user scores)
    - Relevant document excerpts based on chart context
    - Aggregated dataset stats (no raw data)
    
    Args:
        chart_data: Dict containing chart-specific data (subjects, time_points, scores)
        chart_type: Type of chart ('overview', 'subject_detail', 'time_comparison', etc.)
        user_id: User ID for personalization
        db: Database session
    """
    # Extract chart scores
    chart_scores = chart_data.get('scores', {})
    subjects_in_chart = chart_data.get('subjects', [])
    time_points_in_chart = chart_data.get('time_points', [])
    
    # Base instruction - concise for chart comments
    instructions = (
        "Bạn là trợ lý phân tích học tập. "
        "Viết nhận xét ngắn gọn (2-3 câu) về biểu đồ điểm số. "
        "Tập trung vào xu hướng, điểm mạnh/yếu, và gợi ý cải thiện cụ thể."
    )
    
    # Add chart context
    active_structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if active_structure:
        chart_context = f"\n\n📊 BIỂU ĐỒ: {chart_type}\n"
        
        # Format scores compactly
        if chart_scores:
            if chart_type == 'overview':
                # Show all subjects summary
                score_summary = [f"{subj}: {score:.1f}" for subj, score in chart_scores.items()]
                chart_context += f"Điểm hiện tại: {', '.join(score_summary)}\n"
            elif chart_type == 'subject_detail' and subjects_in_chart:
                # Show specific subject across time points
                subject = subjects_in_chart[0] if subjects_in_chart else "Unknown"
                time_scores = [f"{tp}:{chart_scores.get(tp, 'N/A')}" for tp in time_points_in_chart]
                chart_context += f"Môn {subject}: {', '.join(time_scores)}\n"
            else:
                # Generic format
                chart_context += f"Dữ liệu: {chart_scores}\n"
        
        # Add targeted document excerpts (if any)
        if subjects_in_chart:
            doc_keywords = subjects_in_chart + [chart_type]
            structure_docs = db.query(models.CustomStructureDocument).filter(
                models.CustomStructureDocument.structure_id == active_structure.id
            ).limit(3).all()
            
            if structure_docs:
                for doc in structure_docs[:1]:  # Only 1 most relevant doc for charts
                    if doc.extracted_summary:
                        relevant_text = extract_relevant_sections(
                            doc.extracted_summary,
                            doc_keywords,
                            max_tokens=150  # Very limited for charts
                        )
                        if relevant_text and len(relevant_text) > 20:
                            chart_context += f"📄 {doc.file_name}: {relevant_text}\n"
        
        # Add dataset benchmark (only aggregated stats)
        if chart_scores:
            dataset_summary = _get_dataset_summary(db, active_structure.id, chart_scores)
            if dataset_summary:
                chart_context += f"{dataset_summary}\n"
        
        instructions += chart_context
    
    return [{"role": "system", "content": instructions}]


def _derive_score_suggestion(
    db: Session,
    user_id: Optional[int],
    intent: Optional[ScoreUpdateIntent],
) -> Optional[Dict[str, object]]:
    """
    Derive score suggestion from score update intent.
    Uses CustomUserScore and supports multiple structures.
    
    Strategy:
    1. Try active structure first
    2. If no score found, search across all user's structures
    3. Prefer most recently updated score
    """
    if not user_id or not intent:
        return None

    # Get active structure (preferred)
    active_structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    score_entry = None
    structure_used = None
    
    # Try active structure first
    if active_structure:
        score_entry = (
            db.query(models.CustomUserScore)
            .filter(
                models.CustomUserScore.user_id == user_id,
                models.CustomUserScore.structure_id == active_structure.id,
                models.CustomUserScore.subject == intent.subject
            )
            .order_by(models.CustomUserScore.updated_at.desc())
            .first()
        )
        if score_entry:
            structure_used = active_structure
    
    # Fallback: Search across all user's structures
    if not score_entry:
        score_entry = (
            db.query(models.CustomUserScore)
            .filter(
                models.CustomUserScore.user_id == user_id,
                models.CustomUserScore.subject == intent.subject
            )
            .order_by(models.CustomUserScore.updated_at.desc())
            .first()
        )
        if score_entry:
            # Get the structure for this score
            structure_used = db.query(models.CustomTeachingStructure).filter(
                models.CustomTeachingStructure.id == score_entry.structure_id
            ).first()
    
    if not score_entry or not structure_used:
        return None

    suggestion = {
        "score_id": score_entry.id,
        "subject": score_entry.subject,
        "time_point": score_entry.time_point,
        "structure_id": structure_used.id,
        "structure_name": structure_used.structure_name,
        "current_score": score_entry.actual_score,
        "suggested_score": round(intent.new_score, 2),
        "confidence": intent.confidence,
    }

    if intent.old_score is None and score_entry.actual_score is not None:
        suggestion["detected_old_score"] = score_entry.actual_score
    elif intent.old_score is not None:
        suggestion["detected_old_score"] = round(intent.old_score, 2)

    if (
        score_entry.actual_score is not None
        and abs(score_entry.actual_score - suggestion["suggested_score"]) < 1e-6
    ):
        return None

    return suggestion


async def generate_chat_response(
    *,
    db: Session,
    user: Optional[Dict[str, object]],
    message: str,
    session_id: Optional[str],
    request_id: Optional[str] = None,
) -> Dict[str, object]:
    user_id = user.get("user_id") if user else None
    
    contexts = _build_context_blocks(user_id, message, db)
    
    # Prepare conversation history for optimization
    conversation_messages: List[Dict[str, str]] = []
    if session_id:
        sid = None
        try:
            sid = int(session_id)
        except Exception:
            sid = None
        if sid is not None:
            session = db.query(models.ChatSession).filter(models.ChatSession.id == sid).first()
            if session:
                for m in session.messages:
                    role = m.role if m.role in ("user", "assistant", "system") else "user"
                    # Redact PII from historical messages before sending to LLM
                    safe_content = redact_message_content(m.content) if role == "user" else m.content
                    conversation_messages.append({"role": role, "content": safe_content})
    
    # Build optimized prompt with conversation history
    system_messages = _build_prompt(message, contexts, user, db, user_id, conversation_messages)

    # REMOVED: session creation here - moved to after we save user message
    # This ensures we only create sessions when user has sent at least one message

    # REMOVED: context_optimizer (service deleted)
    # Use last 5 messages from conversation history (simplified optimization)
    optimized_history = (conversation_messages[-15:] if len(conversation_messages) > 15 else conversation_messages)
    
    # Redact PII from current user message before sending to LLM
    safe_message = redact_message_content(message)
    
    # Append current user message at end
    optimized_history.append({"role": "user", "content": safe_message})


    # Finalize message list: system messages first, then optimized history
    messages = []
    messages.extend(system_messages)
    messages.extend(optimized_history)

    # Call LLM
    try:
        answer = await _call_remote_llm(messages) or "Hiện tại chưa có phản hồi từ mô hình. Bạn có thể thử lại sau nhé."
    except Exception as exc:  # noqa: BLE001
        # Build a clean fallback message without exposing raw context format
        fallback_parts = []
        for ctx in contexts[:2]:
            ctx_type = (ctx.get("metadata") or {}).get("type", "")
            content = ctx.get("content", "")
            # Skip chat history context to avoid "U: hello A: ..." format in response
            if ctx_type == "chat_history" or not content:
                continue
            # Only include score-related context
            if ctx_type == "score_data":
                fallback_parts.append(f"📊 Điểm số của bạn: {content}")
        
        if fallback_parts:
            answer = (
                "Xin lỗi, hệ thống tạm thời không kết nối được với mô hình ngôn ngữ. "
                "Dưới đây là thông tin có sẵn từ hồ sơ của bạn:\n\n"
                + "\n\n".join(fallback_parts)
            )
        else:
            answer = (
                "Xin lỗi, hệ thống tạm thời không kết nối được với mô hình ngôn ngữ. "
                "Vui lòng thử lại sau hoặc liên hệ hỗ trợ nếu lỗi tiếp tục xảy ra."
            )
        contexts.append({"error": str(exc)})

    # Detect non-sensitive personalization intents and auto-apply
    try:
        pers = detect_personalization_intent(message)
        if pers and user_id:
            field = pers.get("field")
            value = pers.get("value")
            conf = float(pers.get("confidence", 0))
            if conf >= 0.6 and field and value is not None:
                # map field to preference keys
                pref_key = field
                try:
                    set_user_preference(db, user_id, pref_key, value)
                    # update active sessions with new summary
                    from utils.session_utils import SessionManager
                    sessions = SessionManager.get_user_sessions(user_id)
                    # re-query user to build summary
                    user_obj = db.query(models.User).filter(models.User.id == user_id).first()
                    summary = build_user_summary(user_obj) if user_obj else None
                    for s in sessions:
                        try:
                            SessionManager.update_session_fields(s["session_id"], {"preferences_summary": summary})
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass

    persisted_session_id: Optional[str] = None
    # Persist chat messages to session history when possible
    try:
        if session_id:
            # support numeric ids or string ids coming from frontend
            sid = None
            try:
                sid = int(session_id)
            except Exception:
                sid = None

            if sid is not None:
                session = db.query(models.ChatSession).filter(models.ChatSession.id == sid).first()
                if session:
                    # optional ownership check
                    if user_id is None or session.user_id == user_id:
                        # If session has no title yet, generate a concise title from the first user message
                        if not getattr(session, "title", None):
                            try:
                                def _generate_session_title(text: str) -> str:
                                    if not text:
                                        return "Phiên trò chuyện"
                                    t = text.strip()
                                    # try to take first sentence
                                    for sep in (".", "?", "!", "\n"):
                                        if sep in t:
                                            t = t.split(sep)[0]
                                            break
                                    t = t.strip()
                                    if len(t) > 60:
                                        t = t[:57].rsplit(" ", 1)[0] + "..."
                                    # fallback generic
                                    return t or "Phiên trò chuyện"

                                session.title = _generate_session_title(message)
                            except Exception:
                                session.title = "Phiên trò chuyện"

                        user_msg = models.ChatMessage(session_id=session.id, role="user", content=message)
                        assistant_msg = models.ChatMessage(session_id=session.id, role="assistant", content=answer)
                        db.add(user_msg)
                        db.add(assistant_msg)
                        
                        # Generate follow-up question if appropriate
                        follow_up_question = None
                        try:
                            from services.proactive_engagement import ProactiveEngagement
                            engagement = ProactiveEngagement(db)
                            
                            # Count messages to determine if we should ask
                            db.flush()  # Flush to get accurate count
                            db.refresh(session)
                            message_count = len(session.messages)
                            
                            follow_up_question = engagement.generate_follow_up_question(
                                message=message,
                                response=answer,
                                user_id=user_id,
                                conversation_count=message_count
                            )
                            
                            if follow_up_question:
                                # Append follow-up to assistant's answer
                                answer = f"{answer}\n\n{follow_up_question}"
                                assistant_msg.content = answer
                        except Exception as e:
                            import logging
                            logging.getLogger("uvicorn.error").debug(f"Error generating follow-up: {e}")
                        
                        db.commit()
                        persisted_session_id = str(session.id)
        elif user_id:
            # No session_id provided but user is authenticated
            # Create new session and save messages
            try:
                import logging
                logger = logging.getLogger("uvicorn.error")
                logger.info(f"generate_chat_response: creating new session for user_id={user_id}")
                new_session = models.ChatSession(user_id=user_id, title=None)
                db.add(new_session)
                db.flush()  # Get session ID without committing
                
                # Generate title from first user message
                try:
                    def _generate_session_title(text: str) -> str:
                        if not text:
                            return "Phiên trò chuyện"
                        t = text.strip()
                        for sep in (".", "?", "!", "\n"):
                            if sep in t:
                                t = t.split(sep)[0]
                                break
                        t = t.strip()
                        if len(t) > 60:
                            t = t[:57].rsplit(" ", 1)[0] + "..."
                        return t or "Phiên trò chuyện"
                    
                    new_session.title = _generate_session_title(message)
                except Exception:
                    new_session.title = "Phiên trò chuyện"
                
                # Save user and assistant messages
                user_msg = models.ChatMessage(session_id=new_session.id, role="user", content=message)
                assistant_msg = models.ChatMessage(session_id=new_session.id, role="assistant", content=answer)
                db.add(user_msg)
                db.add(assistant_msg)
                db.commit()
                db.refresh(new_session)
                
                persisted_session_id = str(new_session.id)
                logger.info(f"generate_chat_response: created session id={persisted_session_id}")
                
                # Enforce max 20 sessions per user
                try:
                    max_sessions = 20
                    user_sessions = (
                        db.query(models.ChatSession)
                        .filter(models.ChatSession.user_id == user_id)
                        .order_by(models.ChatSession.created_at.desc())
                        .all()
                    )
                    if len(user_sessions) > max_sessions:
                        to_delete = user_sessions[max_sessions:]
                        for s in to_delete:
                            db.delete(s)
                        db.commit()
                except Exception:
                    db.rollback()
            except Exception as e:
                import logging
                logging.getLogger("uvicorn.error").exception(f"Error creating session: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
        
        # Auto-learn personalization after every 5 messages (when session exists)
        if user_id and persisted_session_id:
            try:
                from services.personalization_learner import update_user_personalization
                update_user_personalization(db, user_id, min_messages=5)
            except Exception:
                pass  # Don't fail if personalization learning fails
                        
    except Exception:
        # avoid failing the whole response if persistence fails
        pass

    return {
        "answer": answer,
        "contexts": contexts,
        "session_id": persisted_session_id,
    }


