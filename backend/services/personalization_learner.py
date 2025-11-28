"""
Personalization Learning Service
Analyzes chat sessions to learn user preferences and communication style.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from db import models


class PersonalizationLearner:
    """Analyzes chat sessions to extract personalization preferences."""
    
    def analyze_session_preferences(self, session: models.ChatSession) -> List[str]:
        """
        Analyze a chat session and extract personalization insights.
        Returns a list of learned preference descriptions.
        """
        preferences = []
        
        if not session or not session.messages:
            return preferences
        
        # Analyze message patterns
        user_messages = [msg for msg in session.messages if msg.role == "user"]
        
        if not user_messages:
            return preferences
        
        # Detect communication style
        total_length = sum(len(msg.content) for msg in user_messages)
        avg_length = total_length / len(user_messages) if user_messages else 0
        
        if avg_length < 20:
            preferences.append("Người dùng ưa thích câu trả lời ngắn gọn")
        elif avg_length > 100:
            preferences.append("Người dùng ưa thích giải thích chi tiết")
        
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
            preferences.append("Người dùng sử dụng ngôn ngữ trang trọng")
        elif informal_count > formal_count and informal_count > len(user_messages) * 0.3:
            preferences.append("Người dùng sử dụng ngôn ngữ thân mật")
        
        # Detect topic interests
        study_keywords = ["học", "điểm", "thi", "ôn", "môn"]
        goal_keywords = ["mục tiêu", "kế hoạch", "cần", "muốn"]
        
        study_interest = sum(
            1 for msg in user_messages 
            if any(word in msg.content.lower() for word in study_keywords)
        )
        goal_interest = sum(
            1 for msg in user_messages 
            if any(word in msg.content.lower() for word in goal_keywords)
        )
        
        if study_interest > len(user_messages) * 0.5:
            preferences.append("Quan tâm nhiều đến kết quả học tập")
        if goal_interest > len(user_messages) * 0.3:
            preferences.append("Có xu hướng lập kế hoạch và đặt mục tiêu")
        
        return preferences[:5]  # Limit to top 5 preferences


def get_learned_preferences_display(db: Session, user_id: int) -> List[str]:
    """
    Get learned preferences for a user in display format.
    Returns a list of preference descriptions for UI.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.preferences:
        return []
    
    learned = user.preferences.get("learned")
    if not learned:
        return []
    
    # Handle both list and dict formats (backward compatibility)
    if isinstance(learned, list):
        return learned
    
    # Handle dict format with _description keys
    if isinstance(learned, dict):
        descriptions = []
        for key, value in learned.items():
            if key.endswith("_description"):
                descriptions.append(value)
            elif isinstance(value, str) and not key.startswith("_"):
                descriptions.append(f"{key}: {value}")
        return descriptions
    
    return []


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
    if not learned or not isinstance(learned, list) or len(learned) == 0:
        return ""
    
    # Build personalization prompt
    prefs_text = "\n".join(f"- {pref}" for pref in learned)
    
    return f"\n\n# CÁ NHÂN HÓA:\nNgười dùng có đặc điểm:\n{prefs_text}\nHãy điều chỉnh phong cách trả lời cho phù hợp."


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
    
    # Analyze sessions with enough messages
    all_preferences = []
    learner = PersonalizationLearner()
    
    for session in sessions:
        db.refresh(session)
        if len(session.messages) >= min_messages:
            prefs = learner.analyze_session_preferences(session)
            all_preferences.extend(prefs)
    
    if not all_preferences:
        return
    
    # Deduplicate and keep most recent preferences
    unique_prefs = list(dict.fromkeys(all_preferences))[:5]
    
    # Update user preferences
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        if not user.preferences:
            user.preferences = {}
        
        user.preferences["learned"] = unique_prefs
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "preferences")
        
        db.commit()
