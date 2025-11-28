"""
Context Optimizer Service
Optimizes prompt context to reduce token usage while maintaining quality.
Uses dynamic context selection based on message intent.
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session
import re


class ContextType:
    """Types of context that can be included in prompts."""
    EDUCATIONAL_KNOWLEDGE = "educational_knowledge"
    BENCHMARK_DATA = "benchmark_data"
    USER_PERSONALIZATION = "personalization"
    SIMILAR_STUDENTS = "similar_students"
    CONVERSATION_HISTORY = "conversation_history"


class ContextOptimizer:
    """Optimizes context selection for LLM prompts to reduce token usage."""
    
    # Max tokens for each context type (approximate, 1 token ≈ 4 characters)
    CONTEXT_LIMITS = {
        ContextType.EDUCATIONAL_KNOWLEDGE: 800,   # Giảm từ 1000 → 800
        ContextType.BENCHMARK_DATA: 300,          # Giảm từ 400 → 300
        ContextType.USER_PERSONALIZATION: 150,    # Giữ nguyên
        ContextType.SIMILAR_STUDENTS: 250,        # Giảm từ 300 → 250
        ContextType.CONVERSATION_HISTORY: 600,    # Giảm từ 1000 → 600 (chỉ 3-4 tin nhắn gần nhất)
    }
    
    def __init__(self):
        self.intent_patterns = {
            "score_query": r"(điểm|score|kết quả|thành tích)",
            "comparison": r"(so sánh|mặt bằng|top|xếp hạng|vị trí|so với)",
            "goal_setting": r"(mục tiêu|target|goal|đạt được|trong tương lai)",
            "subject_specific": r"(toán|văn|anh|lý|hóa|sinh|sử|địa|gdcd|công dân|cd)",
            "general_advice": r"(làm sao|như thế nào|tư vấn|gợi ý|khuyên)",
            "personalization": r"(phong cách|sở thích|thích|không thích|thường xuyên|thói quen|nhiều|liên tục)",
        }
    
    def detect_intent(self, message: str) -> List[str]:
        """
        Detect user intent from message to determine what context is needed.
        
        Returns:
            List of intent types detected
        """
        message_lower = message.lower()
        detected_intents = []
        
        for intent, pattern in self.intent_patterns.items():
            if re.search(pattern, message_lower):
                detected_intents.append(intent)
        
        # Default to general advice if no specific intent
        if not detected_intents:
            detected_intents.append("general_advice")
        
        return detected_intents
    
    def select_contexts(self, intents: List[str]) -> List[str]:
        """
        Select which contexts to include based on detected intents.
        
        Args:
            intents: List of detected intent types
        
        Returns:
            List of ContextType to include
        """
        contexts = set()
        
        # Always include personalization if available (very small)
        contexts.add(ContextType.USER_PERSONALIZATION)
        
        for intent in intents:
            if intent == "score_query":
                # Need educational knowledge to explain scores
                contexts.add(ContextType.EDUCATIONAL_KNOWLEDGE)
            
            elif intent == "comparison":
                # Need benchmark data for comparison
                contexts.add(ContextType.BENCHMARK_DATA)
                contexts.add(ContextType.EDUCATIONAL_KNOWLEDGE)
            
            elif intent == "goal_setting":
                # Need similar students and benchmarks
                contexts.add(ContextType.SIMILAR_STUDENTS)
                contexts.add(ContextType.BENCHMARK_DATA)
                contexts.add(ContextType.EDUCATIONAL_KNOWLEDGE)
            
            elif intent == "subject_specific":
                # Need educational knowledge for subject-specific advice
                contexts.add(ContextType.EDUCATIONAL_KNOWLEDGE)
            
            elif intent == "general_advice":
                # Lightweight - just educational knowledge
                contexts.add(ContextType.EDUCATIONAL_KNOWLEDGE)
        
        return list(contexts)
    
    def truncate_text(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
        
        Returns:
            Truncated text
        """
        # Approximate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # Truncate at sentence boundary if possible
        truncated = text[:max_chars]
        
        # Try to find last sentence end
        for sep in [". ", ".\n", "! ", "? "]:
            last_sep = truncated.rfind(sep)
            if last_sep > max_chars * 0.8:  # At least 80% of content
                return truncated[:last_sep + 1]
        
        # Fallback: hard truncate with ellipsis
        return truncated[:max_chars - 3] + "..."
    
    def get_educational_context_summary(self, intents: List[str]) -> str:
        """
        Get a summarized version of educational knowledge based on intents.
        
        Args:
            intents: Detected intents
        
        Returns:
            Relevant educational context (truncated)
        """
        from services.educational_knowledge import get_educational_context
        
        full_context = get_educational_context()
        
        # If goal setting or comparison, need full context
        if "goal_setting" in intents or "comparison" in intents:
            max_tokens = self.CONTEXT_LIMITS[ContextType.EDUCATIONAL_KNOWLEDGE]
        else:
            # For general queries, use half
            max_tokens = self.CONTEXT_LIMITS[ContextType.EDUCATIONAL_KNOWLEDGE] // 2
        
        return self.truncate_text(full_context, max_tokens)
    
    def get_benchmark_context(self, db: Session, user_id: int, intents: List[str]) -> str:
        """
        Get benchmark context only if needed.
        
        Args:
            db: Database session
            user_id: User ID
            intents: Detected intents
        
        Returns:
            Benchmark context or empty string
        """
        # Only fetch if comparison or goal_setting
        if "comparison" not in intents and "goal_setting" not in intents:
            return ""
        
        try:
            from services.dataset_analyzer import get_user_benchmark_summary
            
            benchmark = get_user_benchmark_summary(db, user_id)
            if not benchmark or not benchmark.get("has_data"):
                return ""
            
            summary = benchmark.get("summary", "")
            max_tokens = self.CONTEXT_LIMITS[ContextType.BENCHMARK_DATA]
            
            return self.truncate_text(summary, max_tokens)
        except Exception:
            return ""
    
    def get_similar_students_context(
        self, 
        db: Session, 
        user_id: int, 
        target_average: Optional[float], 
        intents: List[str]
    ) -> str:
        """
        Get similar students context only for goal setting.
        
        Args:
            db: Database session
            user_id: User ID
            target_average: Target GPA (if goal setting)
            intents: Detected intents
        
        Returns:
            Similar students context or empty string
        """
        # Only fetch for goal setting with target
        if "goal_setting" not in intents or not target_average:
            return ""
        
        try:
            from services.dataset_analyzer import find_similar_achievers
            
            similar = find_similar_achievers(db, user_id, target_average, top_k=3)
            if similar.get("status") != "success":
                return ""
            
            summary = similar.get("summary", "")
            max_tokens = self.CONTEXT_LIMITS[ContextType.SIMILAR_STUDENTS]
            
            return self.truncate_text(summary, max_tokens)
        except Exception:
            return ""
    
    def get_personalization_context(self, db: Session, user_id: int) -> str:
        """
        Get personalization context (always lightweight).
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Personalization prompt addition
        """
        try:
            from services.personalization_learner import get_personalization_prompt_addition
            
            addition = get_personalization_prompt_addition(db, user_id)
            max_tokens = self.CONTEXT_LIMITS[ContextType.USER_PERSONALIZATION]
            
            return self.truncate_text(addition, max_tokens)
        except Exception:
            return ""
    
    def optimize_conversation_history(
        self, 
        messages: List[Dict[str, str]], 
        current_message: str
    ) -> List[Dict[str, str]]:
        """
        Optimize conversation history to include only relevant recent messages.
        
        Args:
            messages: Full conversation history
            current_message: Current user message
        
        Returns:
            Optimized message list
        """
        max_tokens = self.CONTEXT_LIMITS[ContextType.CONVERSATION_HISTORY]
        
        # Always include last 3 messages (or fewer if not enough)
        min_messages = 3
        recent_messages = messages[-min_messages:] if len(messages) > min_messages else messages
        
        # Count approximate tokens
        total_chars = sum(len(m.get("content", "")) for m in recent_messages)
        estimated_tokens = total_chars // 4
        
        # If within limit, return all
        if estimated_tokens <= max_tokens:
            return recent_messages
        
        # Otherwise, reduce to last 2 messages only
        return messages[-2:] if len(messages) > 2 else messages
    
    def build_optimized_context(
        self,
        db: Session,
        user_id: Optional[int],
        message: str,
        conversation_history: List[Dict[str, str]],
        target_average: Optional[float] = None
    ) -> Dict[str, str]:
        """
        Build optimized context bundle based on message intent.
        
        Args:
            db: Database session
            user_id: User ID (if authenticated)
            message: Current user message
            conversation_history: Previous messages
            target_average: Optional target for goal setting
        
        Returns:
            Dict with context components
        """
        # Detect intents
        intents = self.detect_intent(message)
        
        # Select needed contexts
        needed_contexts = self.select_contexts(intents)
        
        context_bundle = {
            "intents": intents,
            "educational_knowledge": "",
            "benchmark_data": "",
            "personalization": "",
            "similar_students": "",
            "optimized_history": []
        }
        
        # Build each context component only if needed
        if ContextType.EDUCATIONAL_KNOWLEDGE in needed_contexts:
            context_bundle["educational_knowledge"] = self.get_educational_context_summary(intents)
        
        if user_id:
            if ContextType.BENCHMARK_DATA in needed_contexts:
                context_bundle["benchmark_data"] = self.get_benchmark_context(db, user_id, intents)
            
            if ContextType.USER_PERSONALIZATION in needed_contexts:
                context_bundle["personalization"] = self.get_personalization_context(db, user_id)
            
            if ContextType.SIMILAR_STUDENTS in needed_contexts:
                context_bundle["similar_students"] = self.get_similar_students_context(
                    db, user_id, target_average, intents
                )
        
        # Optimize conversation history
        if ContextType.CONVERSATION_HISTORY in needed_contexts:
            context_bundle["optimized_history"] = self.optimize_conversation_history(
                conversation_history, message
            )
        
        return context_bundle
    
    def estimate_tokens(self, context_bundle: Dict[str, str]) -> Dict[str, int]:
        """
        Estimate token usage for each context component.
        
        Args:
            context_bundle: Bundle from build_optimized_context
        
        Returns:
            Dict with token estimates
        """
        estimates = {}
        
        for key, value in context_bundle.items():
            if key == "optimized_history":
                total_chars = sum(len(m.get("content", "")) for m in value)
                estimates[key] = total_chars // 4
            elif isinstance(value, str):
                estimates[key] = len(value) // 4
            else:
                estimates[key] = 0
        
        estimates["total"] = sum(estimates.values())
        
        return estimates


# Global instance
_optimizer = None

def get_context_optimizer() -> ContextOptimizer:
    """Get singleton context optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = ContextOptimizer()
    return _optimizer
