"""
Hybrid Personalization Learning Service
Uses keyword detection + LLM analysis for intelligent preference extraction.
"""

import json
import logging
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from db import models

logger = logging.getLogger("uvicorn.error")

# ============================================================================
# COMPREHENSIVE TRIGGER KEYWORDS (~250 keywords across 9 categories)
# ============================================================================

TRIGGER_KEYWORDS = {
    # THÓI QUEN HỌC TẬP (~28 keywords)
    "habits": [
        "thường", "hay", "luôn", "hàng ngày", "mỗi ngày", "định kỳ",
        "trước khi", "sau khi", "ôn bài", "làm bài", "học bài",
        "ghi chép", "note", "tóm tắt", "flashcard", "pomodoro",
        "nghỉ ngơi", "giải lao", "tập trung", "mất tập trung",
        "routine", "thói quen", "lịch học", "kế hoạch học", "ôn thi",
        "review", "luyện đề", "làm test", "kiểm tra"
    ],
    
    # SỞ THÍCH (~30 keywords)
    "interests": [
        "thích", "yêu thích", "đam mê", "ghét", "không thích", "chán",
        "hay xem", "hay đọc", "hay nghe", "hay chơi",
        "game", "phim", "nhạc", "sách", "thể thao", "bóng đá", "bóng rổ",
        "vẽ", "code", "lập trình", "youtube", "tiktok", "anime", "manga",
        "nấu ăn", "du lịch", "chụp ảnh", "design", "viết", "blog",
        "guitar", "piano", "rap", "hiphop", "kpop"
    ],
    
    # PHONG CÁCH HỌC (~28 keywords)
    "learning_style": [
        "hiểu", "không hiểu", "khó hiểu", "dễ hiểu",
        "nhìn", "xem", "hình ảnh", "video", "visual", "sơ đồ", "mindmap",
        "nghe", "giảng", "podcast", "audio", "lecture",
        "làm", "thực hành", "tự tay", "experiment", "hands-on",
        "giải thích", "ví dụ", "cụ thể", "tóm tắt", "chi tiết",
        "step by step", "từng bước", "overview", "big picture"
    ],
    
    # TÍNH CÁCH (~28 keywords)
    "personality": [
        "tự", "mình", "một mình", "độc lập", "riêng", "introvert",
        "nhóm", "bạn bè", "cùng", "hợp tác", "teamwork", "extrovert",
        "nhanh", "chậm", "cẩn thận", "kỹ", "đại khái", "chi li",
        "tự tin", "ngại", "sợ", "lo", "e dè", "rụt rè",
        "quyết đoán", "phân vân", "lưỡng lự", "liều", "an toàn"
    ],
    
    # CẢM XÚC (~28 keywords)
    "emotions": [
        "vui", "buồn", "stress", "áp lực", "lo lắng", "căng thẳng",
        "mệt", "kiệt sức", "chán", "năng lượng", "hứng thú", "motivated",
        "tự hào", "thất vọng", "bực", "khó chịu", "thoải mái", "relax",
        "sợ", "lo", "hồi hộp", "excited", "háo hức", "anxious",
        "overwhelmed", "burned out", "chill", "peaceful"
    ],
    
    # MỤC TIÊU (~26 keywords)
    "goals": [
        "muốn", "cần", "mục tiêu", "đạt được", "đạt điểm",
        "cải thiện", "nâng cao", "giỏi hơn", "tốt hơn", "tiến bộ",
        "thi", "đỗ", "vào", "trường", "đại học", "nghề", "career",
        "ước", "mơ", "kế hoạch", "dự định", "tương lai", "dream",
        "target", "milestone", "achievement"
    ],
    
    # LỊCH TRÌNH (~24 keywords)
    "schedule": [
        "sáng", "trưa", "chiều", "tối", "đêm", "khuya",
        "cuối tuần", "thứ 7", "chủ nhật", "ngày thường", "weekday",
        "bận", "rảnh", "thời gian", "lúc nào", "bao lâu",
        "deadline", "hạn", "kịp", "không kịp", "gấp", "urgent",
        "free time", "break"
    ],
    
    # KHÓ KHĂN (~24 keywords)
    "challenges": [
        "khó", "khó khăn", "vấn đề", "không được", "thất bại",
        "yếu", "kém", "điểm thấp", "rớt", "trượt", "fail",
        "không nhớ", "quên", "lú", "confused", "stuck",
        "chưa hiểu", "cần giúp", "làm sao", "như thế nào",
        "struggle", "issue", "problem", "help"
    ],
    
    # GIAO TIẾP (~22 keywords)
    "communication": [
        "nói", "hỏi", "trả lời", "giải thích", "bàn luận",
        "ngắn gọn", "chi tiết", "đơn giản", "phức tạp", "dễ hiểu",
        "ạ", "dạ", "vâng", "nè", "nhé", "oke", "ok",
        "thanks", "cảm ơn", "sorry", "xin lỗi", "please"
    ]
}

# Flatten all keywords for quick lookup
ALL_KEYWORDS: Set[str] = set()
for keywords in TRIGGER_KEYWORDS.values():
    ALL_KEYWORDS.update(keywords)


class HybridPersonalizationLearner:
    """
    Hybrid approach: Keyword detection + LLM analysis.
    Only triggers LLM when meaningful keywords are detected.
    """
    
    def __init__(self, buffer_threshold: int = 8):
        """
        Args:
            buffer_threshold: Number of keyword-containing messages before triggering LLM
        """
        self.buffer_threshold = buffer_threshold
    
    def quick_scan_for_keywords(self, text: str) -> Dict[str, List[str]]:
        """
        Fast keyword scan without LLM.
        Returns dict of category -> matched keywords.
        """
        text_lower = text.lower()
        matches = {}
        
        for category, keywords in TRIGGER_KEYWORDS.items():
            found = [kw for kw in keywords if kw in text_lower]
            if found:
                matches[category] = found
        
        return matches
    
    def has_meaningful_content(self, text: str) -> bool:
        """Check if message contains any trigger keywords."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in ALL_KEYWORDS)
    
    def collect_meaningful_messages(
        self, 
        messages: List[models.ChatMessage]
    ) -> List[str]:
        """Collect messages that contain trigger keywords."""
        meaningful = []
        for msg in messages:
            if msg.role == "user" and self.has_meaningful_content(msg.content):
                meaningful.append(msg.content)
        return meaningful
    
    async def analyze_with_llm(
        self, 
        messages: List[str],
        user_name: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Use LLM to extract structured personalization from messages.
        Only called when we have enough meaningful messages.
        """
        from services.llm_provider import get_llm_provider
        
        if not messages:
            return {}
        
        # Compact prompt to save tokens
        conversation = "\n".join([f"- {msg[:200]}" for msg in messages[:15]])  # Max 15 messages, 200 chars each
        
        prompt = f"""Phân tích tin nhắn của học sinh và trích xuất thông tin cá nhân.

Tin nhắn:
{conversation}

Trả về JSON (chỉ điền những gì RÕ RÀNG được đề cập):
{{
  "learning_style": "visual|auditory|kinesthetic|reading|mixed",
  "personality": ["list các đặc điểm tính cách"],
  "interests": ["list sở thích"],
  "goals": ["list mục tiêu"],
  "challenges": ["list khó khăn"],
  "emotions": "positive|negative|stressed|neutral",
  "schedule_preference": "morning|afternoon|evening|night|flexible",
  "communication_style": "formal|casual|mixed",
  "study_habits": ["list thói quen học"]
}}

Chỉ trả về JSON, không giải thích."""

        try:
            provider = get_llm_provider()
            response = await provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            # Parse response
            result_text = ""
            if isinstance(response, dict):
                candidates = response.get("candidates", [])
                if candidates and isinstance(candidates[0], dict):
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts and isinstance(parts[0], dict):
                        result_text = parts[0].get("text", "")
            
            # Extract JSON from response
            if result_text:
                # Try to find JSON in response
                import re
                json_match = re.search(r'\{[\s\S]*\}', result_text)
                if json_match:
                    return json.loads(json_match.group())
            
            return {}
            
        except Exception as e:
            logger.error(f"[HYBRID_LEARNER] LLM analysis failed: {e}")
            return {}
    
    def convert_llm_result_to_preferences(
        self, 
        llm_result: Dict
    ) -> Dict[str, List[str]]:
        """Convert LLM output to standard preferences format."""
        preferences = {
            "communication_style": [],
            "personality": [],
            "emotions": [],
            "habits": [],
            "schedule": [],
            "interests": [],
            "goals": [],
            "learning_style": [],
            "challenges": []
        }
        
        # Learning style
        if llm_result.get("learning_style"):
            style = llm_result["learning_style"]
            style_map = {
                "visual": "Học tốt qua hình ảnh, video, sơ đồ",
                "auditory": "Học tốt qua nghe giảng, podcast",
                "kinesthetic": "Học tốt qua thực hành, làm bài tập",
                "reading": "Học tốt qua đọc tài liệu",
                "mixed": "Kết hợp nhiều phong cách học"
            }
            if style in style_map:
                preferences["learning_style"].append(style_map[style])
        
        # Personality
        if llm_result.get("personality"):
            for trait in llm_result["personality"][:5]:
                if isinstance(trait, str) and len(trait) > 2:
                    preferences["personality"].append(trait)
        
        # Interests
        if llm_result.get("interests"):
            for interest in llm_result["interests"][:5]:
                if isinstance(interest, str) and len(interest) > 2:
                    preferences["interests"].append(f"Thích {interest}")
        
        # Goals
        if llm_result.get("goals"):
            for goal in llm_result["goals"][:5]:
                if isinstance(goal, str) and len(goal) > 2:
                    preferences["goals"].append(goal)
        
        # Challenges
        if llm_result.get("challenges"):
            for challenge in llm_result["challenges"][:5]:
                if isinstance(challenge, str) and len(challenge) > 2:
                    preferences["challenges"].append(f"Gặp khó khăn: {challenge}")
        
        # Emotions
        if llm_result.get("emotions"):
            emotion = llm_result["emotions"]
            emotion_map = {
                "positive": "Thường có tâm trạng tích cực",
                "negative": "Đang gặp khó khăn về tâm lý",
                "stressed": "Đang chịu áp lực học tập",
                "neutral": "Tâm trạng ổn định"
            }
            if emotion in emotion_map:
                preferences["emotions"].append(emotion_map[emotion])
        
        # Schedule
        if llm_result.get("schedule_preference"):
            schedule = llm_result["schedule_preference"]
            schedule_map = {
                "morning": "Học hiệu quả vào buổi sáng",
                "afternoon": "Học hiệu quả vào buổi chiều",
                "evening": "Học hiệu quả vào buổi tối",
                "night": "Thường học khuya",
                "flexible": "Linh hoạt về thời gian học"
            }
            if schedule in schedule_map:
                preferences["schedule"].append(schedule_map[schedule])
        
        # Communication style
        if llm_result.get("communication_style"):
            style = llm_result["communication_style"]
            style_map = {
                "formal": "Sử dụng ngôn ngữ trang trọng",
                "casual": "Sử dụng ngôn ngữ thân mật",
                "mixed": "Linh hoạt trong giao tiếp"
            }
            if style in style_map:
                preferences["communication_style"].append(style_map[style])
        
        # Study habits
        if llm_result.get("study_habits"):
            for habit in llm_result["study_habits"][:5]:
                if isinstance(habit, str) and len(habit) > 2:
                    preferences["habits"].append(habit)
        
        # Filter empty categories
        return {k: v for k, v in preferences.items() if v}
    
    async def analyze_session(
        self, 
        session: models.ChatSession,
        force_llm: bool = False
    ) -> Dict[str, List[str]]:
        """
        Analyze session with hybrid approach.
        
        Args:
            session: Chat session to analyze
            force_llm: If True, always use LLM analysis
            
        Returns:
            Dict of category -> list of preferences
        """
        if not session or not session.messages:
            return {}
        
        user_messages = [msg for msg in session.messages if msg.role == "user"]
        if not user_messages:
            return {}
        
        # Collect meaningful messages
        meaningful_messages = self.collect_meaningful_messages(user_messages)
        
        # Only trigger LLM if we have enough meaningful content
        if len(meaningful_messages) >= self.buffer_threshold or force_llm:
            logger.info(f"[HYBRID_LEARNER] Triggering LLM analysis with {len(meaningful_messages)} messages")
            llm_result = await self.analyze_with_llm(meaningful_messages)
            if llm_result:
                return self.convert_llm_result_to_preferences(llm_result)
        
        # Fallback: basic keyword analysis (no LLM cost)
        return self._basic_keyword_analysis(user_messages)
    
    def _basic_keyword_analysis(
        self, 
        messages: List[models.ChatMessage]
    ) -> Dict[str, List[str]]:
        """Fallback keyword-based analysis when LLM is not triggered."""
        preferences = {}
        
        all_text = " ".join([msg.content for msg in messages]).lower()
        
        # Simple keyword matching for each category
        category_insights = {
            "interests": [],
            "emotions": [],
            "goals": []
        }
        
        # Check interests
        if any(kw in all_text for kw in ["game", "phim", "nhạc"]):
            category_insights["interests"].append("Có sở thích giải trí")
        if any(kw in all_text for kw in ["thể thao", "bóng", "gym"]):
            category_insights["interests"].append("Thích vận động")
        
        # Check emotions
        if any(kw in all_text for kw in ["stress", "áp lực", "lo"]):
            category_insights["emotions"].append("Đang chịu áp lực")
        if any(kw in all_text for kw in ["vui", "thích", "hay"]):
            category_insights["emotions"].append("Thường tích cực")
        
        # Check goals
        if any(kw in all_text for kw in ["đại học", "thi", "đỗ"]):
            category_insights["goals"].append("Hướng tới kỳ thi quan trọng")
        
        return {k: v for k, v in category_insights.items() if v}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def update_user_personalization_hybrid(
    db: Session, 
    user_id: int,
    session: models.ChatSession
) -> Dict:
    """
    Update user personalization using hybrid approach.
    Called after chat sessions.
    """
    learner = HybridPersonalizationLearner(buffer_threshold=8)
    
    # Analyze session
    new_preferences = await learner.analyze_session(session)
    
    if not new_preferences:
        return {"updated": False, "reason": "No meaningful preferences found"}
    
    # Get user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return {"updated": False, "reason": "User not found"}
    
    if not user.preferences:
        user.preferences = {}
    
    # Merge with existing preferences
    existing = user.preferences.get("learned", {})
    if not isinstance(existing, dict):
        existing = {}
    
    for category, items in new_preferences.items():
        if category not in existing:
            existing[category] = []
        
        # Add new items, avoid duplicates
        for item in items:
            if item not in existing[category]:
                existing[category].append(item)
        
        # Keep max 5 per category
        existing[category] = existing[category][-5:]
    
    # Save
    user.preferences["learned"] = existing
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "preferences")
    db.commit()
    
    logger.info(f"[HYBRID_LEARNER] Updated preferences for user {user_id}: {list(new_preferences.keys())}")
    
    return {
        "updated": True,
        "categories_updated": list(new_preferences.keys()),
        "new_preferences": new_preferences
    }
