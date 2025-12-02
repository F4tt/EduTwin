from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, DateTime, Text, JSON, Boolean, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    age = Column(String, nullable=True)
    preferences = Column('preferences', JSON, nullable=True)
    current_grade = Column(String, nullable=True)
    role = Column(String, nullable=False, default="user")
    first_login_completed = Column(Boolean, nullable=False, server_default=text("false"))
    
    # Track ML config version that user's predictions are based on
    ml_config_version = Column(Integer, nullable=True, default=0)

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
    learning_documents = relationship(
        "LearningDocument",
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
    grade_level = Column(String, nullable=False)  # "10", "11", "12", "TN"
    semester = Column(String, nullable=False)  # "1", "2", "TN"
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
    __tablename__ = "data_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True)
    filename = Column(String, nullable=False)
    total_rows = Column(Integer, nullable=False, default=0)
    imported_rows = Column(Integer, nullable=False, default=0)
    skipped_rows = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    uploader = relationship("User", back_populates="data_imports")
    institution = relationship("Institution")


class LearningDocument(Base):
    __tablename__ = "learning_documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String, nullable=False)
    reference_type = Column(String, nullable=True)
    reference_id = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="learning_documents")
    embeddings = relationship(
        "KnowledgeEmbedding",
        back_populates="document",
        cascade="all, delete-orphan",
    )


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


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("learning_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    vector_id = Column(String, unique=True, nullable=False)
    model = Column(String, nullable=False)
    dimension = Column(Integer, nullable=False)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("LearningDocument", back_populates="embeddings")


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
    __tablename__ = "model_parameters"

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
    __tablename__ = "knn_reference_samples"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True)
    sample_label = Column(String, nullable=True)
    feature_data = Column(JSON, nullable=False)
    metadata_ = Column('metadata', JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
    institution = relationship("Institution")


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


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True)
    institution_name = Column(String, nullable=False)
    institution_type = Column(String, nullable=True)  # "university", "high_school", "training_center", etc.
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    website = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    logo_url = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    metadata_ = Column('metadata', JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class InstitutionModelParameters(Base):
    """Store ML model parameters per institution"""
    __tablename__ = "institution_model_parameters"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, unique=True)
    knn_n = Column(Integer, nullable=False, default=15)
    kr_bandwidth = Column(Float, nullable=False, default=1.25)
    lwlr_tau = Column(Float, nullable=False, default=3.0)
    active_model = Column(String, nullable=False, default='knn')
    pipeline_enabled = Column(Boolean, nullable=False, server_default=text("true"))
    updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TeachingStructure(Base):
    """Store teaching structure configuration per institution"""
    __tablename__ = "teaching_structures"

    id = Column(Integer, primary_key=True, index=True)
    institution_id = Column(Integer, ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False, unique=True)
    num_time_points = Column(Integer, nullable=False)
    num_subjects = Column(Integer, nullable=False)
    time_point_labels = Column(JSON, nullable=False)  # Array of strings
    subject_labels = Column(JSON, nullable=False)  # Array of strings
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    institution = relationship("Institution")
