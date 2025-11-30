"""
Proactive Engagement Service
Generates personalized questions to engage users and learn preferences.
"""

from typing import Optional, Dict, List
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db import models


class ProactiveEngagement:
    """Generates contextual questions to engage users and collect preferences."""
    
    # Câu hỏi mở đầu session mới
    GREETING_TEMPLATES = [
        "Chào {name}! Cùng bắt đầu một cuộc trò chuyện mới nào! Dạo này mọi chuyện có ổn không?",
        "Xin chào {name}! Hôm nay {name} thế nào rồi? Có điều gì muốn chia sẻ không?",
        "Chào buổi {time_of_day} {name}! Tâm trạng hôm nay của {name} ra sao?",
        "Hey {name}! Bắt đầu ngày mới thôi! {name} có kế hoạch gì thú vị không?",
        "Chào {name}! Mình đây, sẵn sàng trò chuyện cùng {name} rồi! Hôm nay có gì đặc biệt không?",
    ]
    
    # Câu hỏi sau khi response
    FOLLOW_UP_CATEGORIES = {
        "emotion": [
            "Nghe có vẻ {emotion_hint}! {name} cảm thấy thế nào về điều này?",
            "Mình hiểu rồi. Tâm trạng của {name} bây giờ ra sao?",
            "Cảm giác của {name} lúc này như nào nhỉ?",
        ],
        "habit": [
            "Thường thì {name} hay làm thế nào trong tình huống này?",
            "{name} có thói quen nào để xử lý việc này không?",
            "Lần trước {name} gặp tình huống tương tự thì đã làm gì?",
        ],
        "schedule": [
            "Hôm nay lịch trình của {name} thế nào? Có bận rộn không?",
            "{name} có dự định gì cho {time_period} sắp tới không?",
            "Thời gian nào trong ngày {name} thường rảnh nhất?",
        ],
        "personality": [
            "Khi gặp việc này, {name} thường là người hành động hay người suy nghĩ kỹ trước?",
            "{name} thích làm việc một mình hay cùng nhóm hơn?",
            "Trong các tình huống như vậy, {name} thường quyết định nhanh hay cần thời gian?",
        ],
        "goals": [
            "Điều này có liên quan đến mục tiêu nào của {name} không?",
            "{name} kỳ vọng gì về kết quả của việc này?",
            "Sau khi hoàn thành việc này, {name} muốn làm gì tiếp theo?",
        ],
        "interests": [
            "Nghe hay đấy! {name} còn thích những gì khác nữa không?",
            "Mình thấy {name} có vẻ quan tâm đến {topic}. Có đúng không?",
            "{name} thường dành thời gian rảnh để làm gì?",
        ],
    }
    
    # Câu hỏi dựa trên context
    CONTEXTUAL_QUESTIONS = {
        "study_stress": [
            "Áp lực học tập có làm {name} mệt mỏi không?",
            "Khi học mệt, {name} thường làm gì để thư giãn?",
        ],
        "exam_coming": [
            "Sắp thi rồi nhỉ? {name} đã sẵn sàng chưa?",
            "Trước mỗi kỳ thi, {name} thường chuẩn bị như thế nào?",
        ],
        "weekend": [
            "Cuối tuần rồi! {name} có kế hoạch gì vui không?",
            "{name} thích dành cuối tuần ở nhà hay đi chơi hơn?",
        ],
        "morning": [
            "Buổi sáng năng lượng chứ? {name} thường làm gì để bắt đầu ngày mới?",
            "{name} là người thức dậy sớm hay ngủ dậy muộn?",
        ],
        "evening": [
            "Buổi tối rồi! {name} đã hoàn thành được bao nhiêu việc hôm nay?",
            "Tối nay {name} có dự định gì không?",
        ],
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_time_of_day(self) -> str:
        """Xác định thời gian trong ngày."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "sáng"
        elif 12 <= hour < 18:
            return "chiều"
        else:
            return "tối"
    
    def _get_time_period(self) -> str:
        """Xác định giai đoạn thời gian."""
        weekday = datetime.now().weekday()
        if weekday >= 5:
            return "cuối tuần"
        else:
            return "tuần này"
    
    def _detect_emotion_hint(self, message: str) -> str:
        """Phát hiện cảm xúc từ tin nhắn."""
        positive_words = ["vui", "hạnh phúc", "tốt", "hay", "tuyệt", "ok", "ổn"]
        negative_words = ["buồn", "tệ", "stress", "mệt", "khó", "lo", "áp lực"]
        
        msg_lower = message.lower()
        
        for word in positive_words:
            if word in msg_lower:
                return "tích cực"
        
        for word in negative_words:
            if word in msg_lower:
                return "có chút khó khăn"
        
        return "thú vị"
    
    def _detect_context(self, message: str, user_id: Optional[int] = None) -> List[str]:
        """Phát hiện context từ tin nhắn và user state."""
        contexts = []
        msg_lower = message.lower()
        
        # Check study-related stress
        stress_keywords = ["stress", "áp lực", "mệt", "khó", "lo"]
        if any(kw in msg_lower for kw in stress_keywords):
            contexts.append("study_stress")
        
        # Check exam mentions
        exam_keywords = ["thi", "kiểm tra", "ôn"]
        if any(kw in msg_lower for kw in exam_keywords):
            contexts.append("exam_coming")
        
        # Check time of day
        hour = datetime.now().hour
        if 5 <= hour < 12:
            contexts.append("morning")
        elif 18 <= hour < 23:
            contexts.append("evening")
        
        # Check weekend
        if datetime.now().weekday() >= 5:
            contexts.append("weekend")
        
        return contexts
    
    def _get_user_name(self, user_id: Optional[int]) -> str:
        """Lấy tên người dùng, fallback về 'bạn'."""
        if not user_id:
            return "bạn"
        
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if user and user.first_name:
            return user.first_name
        return "bạn"
    
    def _get_topic_from_message(self, message: str) -> str:
        """Trích xuất chủ đề từ tin nhắn."""
        study_keywords = ["học", "điểm", "thi"]
        sport_keywords = ["thể thao", "bóng", "chạy"]
        music_keywords = ["nhạc", "hát", "nghe"]
        
        msg_lower = message.lower()
        
        if any(kw in msg_lower for kw in study_keywords):
            return "học tập"
        elif any(kw in msg_lower for kw in sport_keywords):
            return "thể thao"
        elif any(kw in msg_lower for kw in music_keywords):
            return "âm nhạc"
        
        return "điều đó"
    
    def _get_learned_preferences(self, user_id: Optional[int]) -> Dict[str, List[str]]:
        """Lấy learned preferences của user."""
        if not user_id:
            return {}
        
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user or not user.preferences:
            return {}
        
        learned = user.preferences.get("learned", {})
        if isinstance(learned, dict):
            return learned
        
        return {}
    
    def _get_recent_topics(self, user_id: Optional[int]) -> List[str]:
        """Lấy các chủ đề user đã nói gần đây."""
        if not user_id:
            return []
        
        # Get recent messages from last 2 sessions
        recent_sessions = (
            self.db.query(models.ChatSession)
            .filter(models.ChatSession.user_id == user_id)
            .order_by(models.ChatSession.created_at.desc())
            .limit(2)
            .all()
        )
        
        topics = set()
        for session in recent_sessions:
            for msg in session.messages:
                if msg.role == "user":
                    content_lower = msg.content.lower()
                    if any(kw in content_lower for kw in ["học", "điểm", "thi"]):
                        topics.add("học tập")
                    if any(kw in content_lower for kw in ["thể thao", "bóng", "chạy"]):
                        topics.add("thể thao")
                    if any(kw in content_lower for kw in ["mục tiêu", "kế hoạch"]):
                        topics.add("mục tiêu")
                    if any(kw in content_lower for kw in ["stress", "áp lực", "mệt"]):
                        topics.add("cảm xúc")
        
        return list(topics)
    
    def generate_greeting(self, user_id: Optional[int] = None) -> str:
        """
        Tạo câu chào mở đầu cho session mới, cá nhân hóa dựa trên preferences.
        """
        name = self._get_user_name(user_id)
        time_of_day = self._get_time_of_day()
        
        # Get learned preferences to personalize greeting
        learned_prefs = self._get_learned_preferences(user_id)
        
        # Customize greeting based on preferences
        if learned_prefs:
            # Check emotional state
            emotions = learned_prefs.get("emotions", [])
            if any("stress" in e.lower() or "áp lực" in e.lower() for e in emotions):
                # User is stressed - be more supportive
                greetings = [
                    f"Chào {name}! Mình biết {name} đang bận rộn. Hôm nay muốn chia sẻ gì không?",
                    f"Hey {name}! Nghỉ ngơi chút đã nhé. {name} cảm thấy thế nào hôm nay?",
                ]
                return random.choice(greetings)
            
            # Check if user prefers formal communication
            comm_style = learned_prefs.get("communication_style", [])
            if any("trang trọng" in c.lower() for c in comm_style):
                greetings = [
                    f"Xin chào {name}! Rất vui được gặp lại. Hôm nay {name} có điều gì muốn trao đổi không ạ?",
                    f"Chào {name}! Chúc {name} một ngày tốt lành. Có gì mình có thể hỗ trợ không ạ?",
                ]
                return random.choice(greetings)
            
            # Check interests to tailor question
            interests = learned_prefs.get("interests", [])
            if any("học tập" in i.lower() for i in interests):
                greetings = [
                    f"Chào {name}! Học hành dạo này thế nào rồi? Có gì mới không?",
                    f"Hey {name}! Hôm nay học được gì thú vị chưa?",
                ]
                return random.choice(greetings)
        
        # Default greeting
        template = random.choice(self.GREETING_TEMPLATES)
        greeting = template.format(
            name=name,
            time_of_day=time_of_day
        )
        
        return greeting
    
    def generate_follow_up_question(
        self, 
        message: str, 
        response: str,
        user_id: Optional[int] = None,
        conversation_count: int = 0
    ) -> Optional[str]:
        """
        Tạo câu hỏi follow-up dựa trên preferences, lịch sử và context.
        
        Args:
            message: Tin nhắn của user
            response: Response đã tạo
            user_id: ID của user
            conversation_count: Số lượng tin nhắn trong session
            
        Returns:
            Câu hỏi follow-up hoặc None nếu không cần
        """
        # Không hỏi quá nhiều - chỉ hỏi mỗi 3 tin nhắn
        if conversation_count % 3 != 0:
            return None
        
        # Không hỏi nếu user đang hỏi về technical stuff
        technical_keywords = ["làm sao", "cách nào", "hướng dẫn", "giải thích"]
        if any(kw in message.lower() for kw in technical_keywords):
            return None
        
        name = self._get_user_name(user_id)
        emotion_hint = self._detect_emotion_hint(message)
        contexts = self._detect_context(message, user_id)
        topic = self._get_topic_from_message(message)
        time_period = self._get_time_period()
        
        # Get learned preferences and recent topics
        learned_prefs = self._get_learned_preferences(user_id)
        recent_topics = self._get_recent_topics(user_id)
        
        # SMART QUESTIONS based on preferences
        if learned_prefs:
            # If user is stressed, ask supportive questions
            emotions = learned_prefs.get("emotions", [])
            if any("stress" in e.lower() or "áp lực" in e.lower() for e in emotions):
                supportive_questions = [
                    f"{name} có cảm thấy quá tải không? Muốn chia sẻ thêm không?",
                    f"Thấy {name} có vẻ bận. Có thể làm gì giúp {name} thư giãn hơn không?",
                ]
                return random.choice(supportive_questions)
            
            # If user likes goals, ask about planning
            interests = learned_prefs.get("interests", [])
            if any("mục tiêu" in i.lower() or "kế hoạch" in i.lower() for i in interests):
                goal_questions = [
                    f"{name} có kế hoạch cụ thể cho mục tiêu này chưa?",
                    f"Sau khi đạt được điều này, bước tiếp theo của {name} là gì?",
                ]
                return random.choice(goal_questions)
            
            # If user prefers independent work, ask about personal approach
            personality = learned_prefs.get("personality", [])
            if any("độc lập" in p.lower() for p in personality):
                independent_questions = [
                    f"{name} thường tự xử lý việc này hay cần ai đó giúp?",
                    f"Làm một mình có giúp {name} tập trung hơn không?",
                ]
                return random.choice(independent_questions)
            
            # If user is interested in study, follow up on academic topics
            if any("học tập" in i.lower() for i in interests) and "học tập" in recent_topics:
                study_questions = [
                    f"Môn nào {name} đang tập trung nhiều nhất dạo này?",
                    f"Cách học của {name} có hiệu quả không?",
                ]
                return random.choice(study_questions)
        
        # CONTEXTUAL QUESTIONS (when no specific preferences matched)
        if contexts:
            context_key = random.choice(contexts)
            if context_key in self.CONTEXTUAL_QUESTIONS:
                template = random.choice(self.CONTEXTUAL_QUESTIONS[context_key])
                return template.format(name=name)
        
        # FOLLOW UP on recent topics
        if recent_topics and conversation_count > 6:
            topic_follow_ups = {
                "học tập": [
                    f"Nói về học tập, {name} có môn nào cần cải thiện không?",
                    f"Kết quả học tập gần đây của {name} thế nào rồi?",
                ],
                "cảm xúc": [
                    f"Tâm trạng của {name} dạo này có ổn định hơn không?",
                    f"{name} đã tìm được cách giải tỏa stress chưa?",
                ],
                "mục tiêu": [
                    f"Mục tiêu {name} đề ra lần trước tiến triển ra sao?",
                    f"{name} còn gì muốn đạt được trong thời gian tới?",
                ],
            }
            
            for topic_key in recent_topics:
                if topic_key in topic_follow_ups:
                    return random.choice(topic_follow_ups[topic_key])
        
        # DEFAULT QUESTIONS by conversation stage
        if conversation_count < 5:
            # Early stage - hỏi về emotion, habit
            categories = ["emotion", "habit"]
        elif conversation_count < 10:
            # Mid stage - hỏi về schedule, personality
            categories = ["schedule", "personality"]
        else:
            # Late stage - hỏi về goals, interests
            categories = ["goals", "interests"]
        
        category = random.choice(categories)
        template = random.choice(self.FOLLOW_UP_CATEGORIES[category])
        
        return template.format(
            name=name,
            emotion_hint=emotion_hint,
            topic=topic,
            time_period=time_period
        )
    
    def should_ask_follow_up(self, session_id: Optional[int]) -> bool:
        """
        Quyết định có nên hỏi follow-up hay không dựa trên session state.
        """
        if not session_id:
            return False
        
        session = self.db.query(models.ChatSession).filter(
            models.ChatSession.id == session_id
        ).first()
        
        if not session:
            return False
        
        # Đếm số tin nhắn
        message_count = len(session.messages)
        
        # Hỏi ở tin nhắn 3, 6, 9...
        return message_count > 0 and message_count % 3 == 0
