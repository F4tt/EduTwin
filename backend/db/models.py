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
    first_login_completed = Column(Boolean, nullable=False, server_default=text("false"))
    
    # Track ML config version that user's predictions are based on
    ml_config_version = Column(Integer, nullable=True, default=0)

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

    study_scores = relationship(
        "StudyScore",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    data_imports = relationship(
        "DataImportLog",
        back_populates="uploader",
        cascade="all",
    )
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


class StudyScore(Base):
    __tablename__ = "study_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String, nullable=False)
    grade_level = Column(String, nullable=False)  # "10", "11", "12"
    semester = Column(String, nullable=False)  # "1", "2"
    actual_score = Column(Float, nullable=True)
    predicted_score = Column(Float, nullable=True)
    actual_source = Column(String, nullable=True)
    predicted_source = Column(String, nullable=True)
    actual_status = Column(String, nullable=True)
    predicted_status = Column(String, nullable=True)
    actual_updated_at = Column(DateTime(timezone=True), nullable=True)
    predicted_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="study_scores")

    __table_args__ = (
        UniqueConstraint("user_id", "subject", "grade_level", "semester", name="uq_user_subject_grade_semester"),
    )


class DataImportLog(Base):
    __tablename__ = "dataset_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String, nullable=False)
    total_rows = Column(Integer, nullable=False, default=0)
    imported_rows = Column(Integer, nullable=False, default=0)
    skipped_rows = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    uploader = relationship("User", back_populates="data_imports")


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    insight_type = Column(String, nullable=False)  # 'slide_comment', 'chat_response', 'subject_analysis', etc
    context_key = Column(String, nullable=True)     # 'overview_chart', 'Math', 'A00', etc
    content = Column(Text, nullable=False)          # Main AI-generated content
    metadata_ = Column('metadata', JSON, nullable=True)  # Additional data like metrics, version, etc
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="ai_insights")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)
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


class PendingUpdate(Base):
    __tablename__ = "pending_updates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    update_type = Column(String, nullable=False)  # 'profile' | 'score' | 'document'
    field = Column(String, nullable=True)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")


class MLModelConfig(Base):
    __tablename__ = "ml_model_configs"

    id = Column(Integer, primary_key=True, index=True)
    active_model = Column(String, nullable=False, default="knn")  # "knn" | "kernel_regression" | "lwlr"
    # Version increments each time config changes
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ModelParameters(Base):
    __tablename__ = "ml_model_parameters"

    id = Column(Integer, primary_key=True, index=True)
    # KNN parameter: number of neighbors
    knn_n = Column(Integer, nullable=False, default=15)
    # Kernel Regression parameter: bandwidth for Gaussian kernel
    kr_bandwidth = Column(Float, nullable=False, default=1.25)
    # LWLR parameter: tau for tricube kernel (window size control)
    lwlr_tau = Column(Float, nullable=False, default=3.0)
    # Version increments each time parameters change
    version = Column(Integer, nullable=False, default=1)
    # Who last updated these parameters
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class KNNReferenceSample(Base):
    __tablename__ = "reference_dataset"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    sample_label = Column(String, nullable=True)
    feature_data = Column(JSON, nullable=False)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")


class CustomTeachingStructure(Base):
    __tablename__ = "custom_teaching_structures"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    structure_name = Column(String, nullable=False)  # User-defined name for the structure
    num_time_points = Column(Integer, nullable=False)
    num_subjects = Column(Integer, nullable=False)
    time_point_labels = Column(JSON, nullable=False)  # List of time point names
    subject_labels = Column(JSON, nullable=False)  # List of subject names
    current_time_point = Column(String, nullable=True)  # Currently selected time point for score input
    pipeline_enabled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)  # Currently selected structure
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")


class CustomDatasetSample(Base):
    __tablename__ = "custom_reference_dataset"

    id = Column(Integer, primary_key=True, index=True)
    structure_id = Column(Integer, ForeignKey("custom_teaching_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sample_name = Column(String, nullable=True)
    score_data = Column(JSON, nullable=False)  # Dict of subject_timepoint: score
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
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


class LearningGoal(Base):
    __tablename__ = "learning_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_average = Column(Float, nullable=False)
    target_semester = Column(String, nullable=False)
    target_grade_level = Column(String, nullable=False)
    predicted_scores = Column(JSON, nullable=True)
    trajectory_data = Column(JSON, nullable=True)
    ai_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
