"""
PII Redaction Service

Ẩn danh hóa thông tin cá nhân (PII) trước khi gửi tới LLM để bảo vệ privacy.
"""

import re
from typing import Dict, Any, Optional
import hashlib


class PIIRedactor:
    """Service to redact Personal Identifiable Information (PII) from text and data."""
    
    @staticmethod
    def hash_value(value: str, salt: str = "edutwin_salt") -> str:
        """
        Hash a value using SHA-256 to create consistent anonymized ID.
        
        Args:
            value: Original value to hash
            salt: Salt for hashing
            
        Returns:
            Hashed string (first 12 chars for readability)
        """
        if not value:
            return "UNKNOWN"
        hashed = hashlib.sha256(f"{salt}_{value}".encode()).hexdigest()
        return f"USER_{hashed[:8].upper()}"
    
    @staticmethod
    def redact_phone(phone: Optional[str]) -> str:
        """
        Redact phone number.
        
        Example: 0912345678 -> PHONE_XXXX5678
        """
        if not phone:
            return "PHONE_UNKNOWN"
        # Keep last 4 digits
        cleaned = re.sub(r'\D', '', phone)
        if len(cleaned) >= 4:
            return f"PHONE_XXXX{cleaned[-4:]}"
        return "PHONE_REDACTED"
    
    @staticmethod
    def redact_email(email: Optional[str]) -> str:
        """
        Redact email address.
        
        Example: nguyen@gmail.com -> n***n@g***l.com
        """
        if not email or '@' not in email:
            return "EMAIL_UNKNOWN"
        
        try:
            username, domain = email.split('@')
            # Keep first and last char of username
            if len(username) > 2:
                username_redacted = f"{username[0]}***{username[-1]}"
            else:
                username_redacted = "***"
            
            # Keep first char of domain name
            domain_parts = domain.split('.')
            if len(domain_parts[0]) > 1:
                domain_redacted = f"{domain_parts[0][0]}***{'.'.join(domain_parts[1:])}"
            else:
                domain_redacted = domain
            
            return f"{username_redacted}@{domain_redacted}"
        except:
            return "EMAIL_REDACTED"
    
    @staticmethod
    def redact_address(address: Optional[str]) -> str:
        """
        Redact full address, keep only district/city level.
        
        Example: 35 Lê Lợi, Q1, HCM -> ADDR_Q1_HCM
        """
        if not address:
            return "ADDR_UNKNOWN"
        
        # Extract district and city (simple heuristic)
        # Look for patterns like Q1, Quận 1, District 1
        district_match = re.search(r'(Q\d+|Quận \d+|District \d+)', address, re.IGNORECASE)
        city_match = re.search(r'(HCM|Hà Nội|Đà Nẵng|TP\.|Thành phố)', address, re.IGNORECASE)
        
        parts = []
        if district_match:
            parts.append(district_match.group(1).replace(' ', ''))
        if city_match:
            parts.append(city_match.group(1).replace(' ', ''))
        
        if parts:
            return f"ADDR_{'_'.join(parts)}"
        return "ADDR_REDACTED"
    
    @classmethod
    def redact_user_data(cls, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact all PII from user data dictionary.
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            Dictionary with redacted PII, safe to send to LLM
        """
        redacted = {}
        
        # Handle name
        if 'first_name' in user_data and 'last_name' in user_data:
            full_name = f"{user_data.get('last_name', '')} {user_data.get('first_name', '')}".strip()
            redacted['user_id'] = cls.hash_value(full_name)
        elif 'username' in user_data:
            redacted['user_id'] = cls.hash_value(user_data['username'])
        elif 'id' in user_data:
            redacted['user_id'] = f"USER_{user_data['id']}"
        else:
            redacted['user_id'] = "USER_UNKNOWN"
        
        # Redact sensitive fields
        if 'email' in user_data:
            redacted['email'] = cls.redact_email(user_data['email'])
        
        if 'phone' in user_data:
            redacted['phone'] = cls.redact_phone(user_data['phone'])
        
        if 'address' in user_data:
            redacted['address'] = cls.redact_address(user_data['address'])
        
        # Keep non-sensitive data as-is
        safe_fields = ['age', 'current_grade', 'role']
        for field in safe_fields:
            if field in user_data:
                redacted[field] = user_data[field]
        
        return redacted
    
    @staticmethod
    def redact_text(text: str) -> str:
        """
        Redact PII patterns from free text.
        
        Args:
            text: Original text that may contain PII
            
        Returns:
            Text with PII redacted
        """
        if not text:
            return text
        
        # Redact phone numbers (Vietnam format)
        text = re.sub(r'\b0\d{9,10}\b', 'PHONE_REDACTED', text)
        text = re.sub(r'\b\+84\d{9,10}\b', 'PHONE_REDACTED', text)
        
        # Redact emails
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL_REDACTED', text)
        
        # Redact Vietnamese names (simple pattern - may need refinement)
        # Pattern: Capitalized Vietnamese words (2-4 words)
        # Example: Nguyễn Văn A, Trần Thị B
        text = re.sub(
            r'\b([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ][a-zàáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]+\s){2,3}[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴỶỸ][a-zàáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]+\b',
            'NAME_REDACTED',
            text
        )
        
        return text
    
    @classmethod
    def prepare_llm_context(cls, user_data: Dict[str, Any], include_scores: bool = False) -> str:
        """
        Prepare safe context string for LLM without exposing PII.
        
        Args:
            user_data: Original user data
            include_scores: Whether to include score information
            
        Returns:
            Safe context string for LLM prompt
        """
        redacted = cls.redact_user_data(user_data)
        
        context_parts = [
            f"Đang hỗ trợ học sinh {redacted['user_id']}"
        ]
        
        if 'age' in redacted and redacted['age']:
            context_parts.append(f"Độ tuổi: {redacted['age']}")
        
        if 'current_grade' in redacted and redacted['current_grade']:
            context_parts.append(f"Lớp: {redacted['current_grade']}")
        
        # Add location info if available (already redacted)
        if 'address' in redacted and redacted['address'] != 'ADDR_UNKNOWN':
            context_parts.append(f"Khu vực: {redacted['address']}")
        
        return ". ".join(context_parts) + "."


# Singleton instance
pii_redactor = PIIRedactor()


def redact_user_for_llm(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to redact user data.
    
    Usage:
        safe_data = redact_user_for_llm(user.__dict__)
    """
    return pii_redactor.redact_user_data(user_data)


def prepare_safe_llm_prompt(base_prompt: str, user_data: Dict[str, Any]) -> str:
    """
    Prepare LLM prompt with redacted user context.
    
    Usage:
        safe_prompt = prepare_safe_llm_prompt(
            "Hãy tư vấn cho học sinh này:",
            user.__dict__
        )
    """
    context = pii_redactor.prepare_llm_context(user_data)
    return f"{base_prompt}\n\nThông tin học sinh (đã ẩn danh):\n{context}"


def redact_message_content(message: str) -> str:
    """
    Redact PII from message content before sending to LLM.
    
    Usage:
        safe_message = redact_message_content(user_message)
    """
    return pii_redactor.redact_text(message)
