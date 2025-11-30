"""
Personalization Learning Service
Analyzes chat sessions to learn user preferences and communication style.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from db import models


class PersonalizationLearner:
    """Analyzes chat sessions to extract personalization preferences."""
    
    def analyze_session_preferences(self, session: models.ChatSession) -> Dict[str, any]:
        """
        Analyze a chat session and extract comprehensive personalization insights.
        Returns a dictionary with categorized preferences.
        """
        preferences = {
            "communication_style": [],
            "personality": [],
            "emotions": [],
            "habits": [],
            "schedule": [],
            "interests": [],
            "goals": []
        }
        
        if not session or not session.messages:
            return preferences
        
        # Analyze message patterns
        user_messages = [msg for msg in session.messages if msg.role == "user"]
        
        if not user_messages:
            return preferences
        
        # 1. COMMUNICATION STYLE
        total_length = sum(len(msg.content) for msg in user_messages)
        avg_length = total_length / len(user_messages) if user_messages else 0
        
        if avg_length < 20:
            preferences["communication_style"].append("Ưa thích câu trả lời ngắn gọn")
        elif avg_length > 100:
            preferences["communication_style"].append("Ưa thích giải thích chi tiết")
        
        # Detect formality
        formal_words = ["xin", "ạ", "dạ", "thưa", "kính"]
        informal_words = ["nè", "nhé", "ừ", "oke", "ok"]
        
        formal_count = sum(
            1 for msg in user_messages 
            if any(word in msg.content.lower() for word in formal_words)
        )
        informal_count = sum(
            1 for msg in user_messages 
            if any(word in msg.content.lower() for word in informal_words)
        )
        
        if formal_count > informal_count and formal_count > len(user_messages) * 0.3:
            preferences["communication_style"].append("Sử dụng ngôn ngữ trang trọng")
        elif informal_count > formal_count and informal_count > len(user_messages) * 0.3:
            preferences["communication_style"].append("Sử dụng ngôn ngữ thân mật")
        
        # 2. PERSONALITY TRAITS
        action_words = ["làm", "thực hiện", "bắt đầu", "làm luôn"]
        thinking_words = ["suy nghĩ", "cân nhắc", "xem xét", "phân tích"]
        
        action_count = sum(1 for msg in user_messages if any(w in msg.content.lower() for w in action_words))
        thinking_count = sum(1 for msg in user_messages if any(w in msg.content.lower() for w in thinking_words))
        
        if action_count > thinking_count and action_count > 2:
            preferences["personality"].append("Hướng hành động, thích làm ngay")
        elif thinking_count > action_count and thinking_count > 2:
            preferences["personality"].append("Thích suy nghĩ kỹ trước khi hành động")
        
        # Independence vs collaboration
        solo_words = ["tự", "mình", "một mình", "riêng"]
        team_words = ["nhóm", "cùng", "chúng mình", "bạn bè"]
        
        solo_count = sum(1 for msg in user_messages if any(w in msg.content.lower() for w in solo_words))
        team_count = sum(1 for msg in user_messages if any(w in msg.content.lower() for w in team_words))
        
        if solo_count > team_count and solo_count > 1:
            preferences["personality"].append("Thích làm việc độc lập")
        elif team_count > solo_count and team_count > 1:
            preferences["personality"].append("Thích làm việc nhóm")
        
        # 3. EMOTIONS
        emotion_keywords = {
            "vui": ["vui", "hạnh phúc", "tuyệt", "hay", "thích"],
            "stress": ["stress", "áp lực", "lo", "căng thẳng"],
            "mệt": ["mệt", "chán", "buồn tẻ"],
            "hứng_thú": ["thích", "hay", "tuyệt", "tốt", "ok"],
        }
        
        for emotion, keywords in emotion_keywords.items():
            count = sum(1 for msg in user_messages if any(kw in msg.content.lower() for kw in keywords))
            if count > len(user_messages) * 0.2:
                if emotion == "vui":
                    preferences["emotions"].append("Thường trong trạng thái tích cực")
                elif emotion == "stress":
                    preferences["emotions"].append("Đang có áp lực học tập")
                elif emotion == "mệt":
                    preferences["emotions"].append("Cần thư giãn và nghỉ ngơi")
        
        # 4. HABITS & SCHEDULE
        time_keywords = {
            "sáng": ["sáng", "buổi sáng", "sáng sớm"],
            "tối": ["tối", "buổi tối", "đêm"],
            "cuối_tuần": ["cuối tuần", "thứ 7", "chủ nhật"],
        }
        
        for time_period, keywords in time_keywords.items():
            count = sum(1 for msg in user_messages if any(kw in msg.content.lower() for kw in keywords))
            if count > 1:
                if time_period == "sáng":
                    preferences["schedule"].append("Thường hoạt động vào buổi sáng")
                elif time_period == "tối":
                    preferences["schedule"].append("Thường hoạt động vào buổi tối")
                elif time_period == "cuối_tuần":
                    preferences["schedule"].append("Quan tâm đến kế hoạch cuối tuần")
        
        # Study habits
        study_habit_keywords = {
            "ôn_trước": ["ôn trước", "chuẩn bị trước", "học trước"],
            "làm_bài": ["làm bài", "luyện tập", "thực hành"],
            "nghỉ_giải_lao": ["nghỉ", "giải lao", "thư giãn"],
        }
        
        for habit, keywords in study_habit_keywords.items():
            count = sum(1 for msg in user_messages if any(kw in msg.content.lower() for kw in keywords))
            if count > 0:
                if habit == "ôn_trước":
                    preferences["habits"].append("Có thói quen ôn bài trước")
                elif habit == "làm_bài":
                    preferences["habits"].append("Thường xuyên làm bài tập")
                elif habit == "nghỉ_giải_lao":
                    preferences["habits"].append("Biết cân bằng học tập và nghỉ ngơi")
        
        # 5. INTERESTS
        interest_keywords = {
            "học_tập": ["học", "điểm", "thi", "ôn", "môn học"],
            "mục_tiêu": ["mục tiêu", "kế hoạch", "định hướng"],
            "thể_thao": ["thể thao", "bóng", "chạy", "gym"],
            "âm_nhạc": ["nhạc", "hát", "nghe nhạc"],
            "đọc_sách": ["sách", "đọc", "truyện"],
        }
        
        for interest, keywords in interest_keywords.items():
            count = sum(1 for msg in user_messages if any(kw in msg.content.lower() for kw in keywords))
            if count > len(user_messages) * 0.3:
                if interest == "học_tập":
                    preferences["interests"].append("Quan tâm nhiều đến kết quả học tập")
                elif interest == "mục_tiêu":
                    preferences["interests"].append("Thích lập kế hoạch và mục tiêu")
                elif interest == "thể_thao":
                    preferences["interests"].append("Yêu thích thể thao")
                elif interest == "âm_nhạc":
                    preferences["interests"].append("Thích âm nhạc")
                elif interest == "đọc_sách":
                    preferences["interests"].append("Thích đọc sách")
        
        # 6. GOALS
        goal_keywords = ["muốn", "cần", "đạt", "cải thiện", "nâng cao"]
        goal_count = sum(1 for msg in user_messages if any(kw in msg.content.lower() for kw in goal_keywords))
        
        if goal_count > len(user_messages) * 0.3:
            preferences["goals"].append("Có xu hướng đặt mục tiêu rõ ràng")
        
        # Filter empty categories
        return {k: v for k, v in preferences.items() if v}
    
    def preferences_to_summary(self, preferences: Dict[str, List[str]]) -> List[str]:
        """Convert structured preferences to flat list for backward compatibility."""
        summary = []
        for category, items in preferences.items():
            summary.extend(items)
        return summary[:10]  # Top 10 insights


def get_learned_preferences_display(db: Session, user_id: int) -> Dict[str, List[str]]:
    """
    Get learned preferences for a user in structured format.
    Returns a dict with categorized preference descriptions for UI.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.preferences:
        return {}
    
    learned = user.preferences.get("learned")
    if not learned:
        return {}
    
    # Handle dict format (new structure)
    if isinstance(learned, dict):
        return learned
    
    # Handle list format (backward compatibility) - convert to dict
    if isinstance(learned, list):
        return {"general": learned}
    
    return {}


def get_personalization_prompt_addition(db: Session, user_id: int) -> str:
    """
    Get personalization context to add to the LLM prompt.
    This applies to ALL chat sessions for the user.
    
    Returns:
        A string with personalization instructions based on user preferences
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.preferences:
        return ""
    
    learned = user.preferences.get("learned")
    if not learned:
        return ""
    
    # Build personalization prompt from structured preferences
    sections = []
    
    if isinstance(learned, dict):
        category_names = {
            "communication_style": "Phong cách giao tiếp",
            "personality": "Tính cách",
            "emotions": "Cảm xúc",
            "habits": "Thói quen",
            "schedule": "Lịch trình",
            "interests": "Sở thích",
            "goals": "Mục tiêu"
        }
        
        for category, items in learned.items():
            if items and isinstance(items, list):
                category_display = category_names.get(category, category)
                items_text = ", ".join(items)
                sections.append(f"**{category_display}**: {items_text}")
    elif isinstance(learned, list):
        # Backward compatibility
        prefs_text = "\n".join(f"- {pref}" for pref in learned)
        return f"\n\n# CÁ NHÂN HÓA:\nNgười dùng có đặc điểm:\n{prefs_text}\nHãy điều chỉnh phong cách trả lời cho phù hợp."
    
    if not sections:
        return ""
    
    profile_text = "\n".join(sections)
    return (
        f"\n\n# CÁ NHÂN HÓA:\n"
        f"Đây là profile của người dùng:\n{profile_text}\n\n"
        f"Hãy điều chỉnh phong cách trả lời, ngôn từ và nội dung cho phù hợp với đặc điểm này. "
        f"Thể hiện sự quan tâm và cá nhân hóa trải nghiệm."
    )


def update_user_personalization(db: Session, user_id: int, min_messages: int = 5):
    """
    Update user personalization based on recent chat sessions.
    Called periodically after user sends messages.
    
    Args:
        db: Database session
        user_id: User ID to update
        min_messages: Minimum number of messages in a session before learning
    """
    # Get recent chat sessions
    sessions = (
        db.query(models.ChatSession)
        .filter(models.ChatSession.user_id == user_id)
        .order_by(models.ChatSession.created_at.desc())
        .limit(3)  # Analyze last 3 sessions
        .all()
    )
    
    if not sessions:
        return
    
    # Analyze sessions with enough messages and merge preferences
    merged_preferences = {
        "communication_style": set(),
        "personality": set(),
        "emotions": set(),
        "habits": set(),
        "schedule": set(),
        "interests": set(),
        "goals": set()
    }
    
    learner = PersonalizationLearner()
    
    for session in sessions:
        db.refresh(session)
        if len(session.messages) >= min_messages:
            prefs = learner.analyze_session_preferences(session)
            # Merge all categories
            for category, items in prefs.items():
                if category in merged_preferences:
                    merged_preferences[category].update(items)
    
    # Convert sets to lists and filter empty
    final_preferences = {
        k: list(v)[:5]  # Max 5 items per category
        for k, v in merged_preferences.items() 
        if v
    }
    
    if not final_preferences:
        return
    
    # Update user preferences
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        if not user.preferences:
            user.preferences = {}
        
        user.preferences["learned"] = final_preferences
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "preferences")
        
        db.commit()
