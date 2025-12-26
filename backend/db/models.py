from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, DateTime, Text, JSON, Boolean, text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    # Encrypted fields - stored as _encrypted_* columns
    _encrypted_email = Column('email', String, nullable=True)
    _encrypted_phone = Column('phone', String, nullable=True)
    _encrypted_address = Column('address', String, nullable=True)
    
    age = Column(String, nullable=True)
    preferences = Column('preferences', JSON, nullable=True)
    current_grade = Column(String, nullable=True)
    role = Column(String, nullable=False, default="user")

    # Transparent encryption/decryption properties
    @hybrid_property
    def email(self):
        """Decrypt email on access."""
        if not self._encrypted_email:
            return None
        try:
            from utils.encryption import decrypt_field
            return decrypt_field(self._encrypted_email)
        except Exception:
            # If decryption fails, return None and log warning
            # This can happen during migration or if key changed
            return None
    
    @email.setter
    def email(self, value):
        """Encrypt email on assignment."""
        if value is None:
            self._encrypted_email = None
        else:
            from utils.encryption import encrypt_field
            self._encrypted_email = encrypt_field(value)
    
    @hybrid_property
    def phone(self):
        """Decrypt phone on access."""
        if not self._encrypted_phone:
            return None
        try:
            from utils.encryption import decrypt_field
            return decrypt_field(self._encrypted_phone)
        except Exception:
            return None
    
    @phone.setter
    def phone(self, value):
        """Encrypt phone on assignment."""
        if value is None:
            self._encrypted_phone = None
        else:
            from utils.encryption import encrypt_field
            self._encrypted_phone = encrypt_field(value)
    
    @hybrid_property
    def address(self):
        """Decrypt address on access."""
        if not self._encrypted_address:
            return None
        try:
            from utils.encryption import decrypt_field
            return decrypt_field(self._encrypted_address)
        except Exception:
            return None
    
    @address.setter
    def address(self, value):
        """Encrypt address on assignment."""
        if value is None:
            self._encrypted_address = None
        else:
            from utils.encryption import encrypt_field
            self._encrypted_address = encrypt_field(value)


    ai_insights = relationship(
        "AIInsight",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    # JSON field for storing uploaded documents
    uploaded_documents = Column(JSON, nullable=True, default=list)




class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    structure_id = Column(Integer, ForeignKey("custom_teaching_structures.id", ondelete="CASCADE"), nullable=True, index=True)  # Structure this insight belongs to
    insight_type = Column(String, nullable=False)  # 'slide_comment', 'chat_response', 'subject_analysis', etc
    context_key = Column(String, nullable=True)     # 'overview_chart', 'Math', 'A00', etc
    content = Column(Text, nullable=False)          # Main AI-generated content
    metadata_ = Column('metadata', JSON, nullable=True)  # Additional data like metrics, version, etc
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="ai_insights")
    structure = relationship("CustomTeachingStructure")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)
    mode = Column(String, nullable=True, default='chat')  # 'chat', 'learning', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ChatSession", back_populates="messages")






class CustomTeachingStructure(Base):
    __tablename__ = "custom_teaching_structures"

    id = Column(Integer, primary_key=True, index=True)
    # user_id removed - structure is now global
    structure_name = Column(String, nullable=False)  # Admin-defined name for the structure
    num_time_points = Column(Integer, nullable=False)
    num_subjects = Column(Integer, nullable=False)
    time_point_labels = Column(JSON, nullable=False)  # List of time point names
    subject_labels = Column(JSON, nullable=False)  # List of subject names
    scale_type = Column(String, nullable=False, server_default='0-10')  # '0-10', '0-100', '0-10000', 'A-F', 'GPA'
    # current_time_point removed - each user manages their own time point
    pipeline_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=False)  # Only one can be active globally
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Unique constraint: only one structure can be active
    __table_args__ = (
        Index('ix_custom_teaching_structures_single_active', 'is_active', unique=True, postgresql_where=text('is_active = true')),
    )


class CustomDatasetSample(Base):
    __tablename__ = "custom_reference_dataset"

    id = Column(Integer, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey("custom_teaching_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    # user_id removed - dataset is global per structure
    sample_name = Column(String, nullable=True)
    score_data = Column(JSON, nullable=False)  # Dict of subject_timepoint: score
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    structure = relationship("CustomTeachingStructure")


class CustomUserScore(Base):
    __tablename__ = "custom_user_scores"

    id = Column(Integer, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey("custom_teaching_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String, nullable=False)
    time_point = Column(String, nullable=False)
    actual_score = Column(Float, nullable=True)
    predicted_score = Column(Float, nullable=True)
    predicted_source = Column(String, nullable=True)  # Model used: knn, kernel_regression, lwlr
    predicted_status = Column(String, nullable=True)  # Status: active, replaced
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    structure = relationship("CustomTeachingStructure")

    __table_args__ = (
        # Unique constraint: one score per (user, structure, subject, time_point)
        Index('ix_custom_user_score_unique', 'user_id', 'structure_id', 'subject', 'time_point', unique=True),
    )


class CustomStructureDocument(Base):
    """Reference documents for custom teaching structures (PDFs, DOCX, TXT).
    Each structure can have multiple reference documents to provide context for AI analysis.
    Documents are processed to extract key information and reduce token usage.
    """
    __tablename__ = "custom_structure_documents"

    id = Column(Integer, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey("custom_teaching_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String, nullable=False)  # Original filename
    file_type = Column(String, nullable=False)  # 'pdf', 'docx', 'txt'
    file_size = Column(Integer, nullable=True)  # Size in bytes
    original_content = Column(Text, nullable=True)  # Full extracted text (for reference)
    extracted_summary = Column(Text, nullable=False)  # LLM-extracted key points (optimized for context)
    extraction_method = Column(String, nullable=True, default='llm_summary')  # Method used: llm_summary, embeddings, etc
    metadata_ = Column('metadata', JSON, nullable=True)  # Additional info: page count, sections, etc
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    structure = relationship("CustomTeachingStructure")
    uploader = relationship("User")


class ModelParameters(Base):
    """ML model parameters (KNN, Kernel Regression, LWLR)"""
    __tablename__ = "ml_model_parameters"

    id = Column(Integer, primary_key=True, index=True)
    knn_n = Column(Integer, nullable=False, server_default='15')
    kr_bandwidth = Column(Float, nullable=False, server_default='1.25')
    lwlr_tau = Column(Float, nullable=False, server_default='3.0')
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    updater = relationship("User")


class MLModelConfig(Base):
    """ML model configuration - stores which model is currently active"""
    __tablename__ = "ml_model_config"

    id = Column(Integer, primary_key=True, index=True)
    active_model = Column(String, nullable=False, server_default='knn')  # 'knn', 'kernel_regression', 'lwlr'
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    updater = relationship("User")


class UserStructurePreference(Base):
    """Store user preferences per structure (e.g., current_timepoint)"""
    __tablename__ = "user_structure_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    structure_id = Column(Integer, ForeignKey("custom_teaching_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    current_timepoint = Column(String, nullable=True)  # Current time point for this user in this structure
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    structure = relationship("CustomTeachingStructure")

    __table_args__ = (
        # Unique constraint: one preference row per (user, structure)
        Index('ix_user_structure_pref_unique', 'user_id', 'structure_id', unique=True),
    )


# LearningGoal model removed - feature deprecated

