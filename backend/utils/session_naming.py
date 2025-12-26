"""
Session naming utilities
Generate smart session titles from first user message
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_keywords(text: str, max_words: int = 5) -> str:
    """
    Extract key words from text for session title
    Fallback if LLM fails
    """
    # Remove special characters
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Split and filter
    words = text.split()
    
    # Remove common stop words (Vietnamese + English)
    stop_words = {
        'là', 'của', 'và', 'có', 'trong', 'cho', 'với', 'được', 'các', 'một', 'này',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'has', 'have',
        'tôi', 'bạn', 'mình', 'giúp', 'hỏi', 'nào', 'gì', 'như', 'thế', 'sao'
    }
    
    keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]
    
    # Take first N words
    return ' '.join(keywords[:max_words]) if keywords else text[:30]


async def generate_session_title(first_message: str, llm_provider=None) -> str:
    """
    Generate a descriptive session title from first user message
    
    Args:
        first_message: User's first message
        llm_provider: LLM provider for smart summarization
        
    Returns:
        Session title (max 50 chars)
    """
    # Limit input length
    first_message = first_message[:500]
    
    # Try LLM summarization first
    if llm_provider:
        try:
            prompt = f"""Tóm tắt câu hỏi sau thành tiêu đề ngắn gọn (tối đa 5-7 từ):

Câu hỏi: "{first_message}"

Chỉ trả lời tiêu đề, không giải thích. Ví dụ:
- "Tính diện tích hình tròn" 
- "Quá trình quang hợp"
- "Lịch sử Việt Nam"
- "Giải phương trình bậc 2"
"""
            
            messages = [{"role": "user", "content": prompt}]
            response = await llm_provider.chat(messages, temperature=0.3)
            
            if response:
                # Extract text from response
                if isinstance(response, dict):
                    title = response.get('content', '').strip()
                elif isinstance(response, str):
                    title = response.strip()
                else:
                    title = str(response).strip()
                
                # Clean up
                title = title.strip('"\'').strip()
                
                # Validate length
                if title and len(title) <= 50:
                    logger.info(f"Generated session title via LLM: {title}")
                    return title
                    
        except Exception as e:
            logger.warning(f"LLM title generation failed: {e}")
    
    # Fallback: Extract keywords
    title = extract_keywords(first_message, max_words=6)
    
    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."
    
    logger.info(f"Generated session title via keywords: {title}")
    return title or "New Chat"
