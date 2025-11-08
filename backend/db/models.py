from sqlalchemy import Column, Integer, String, Float, ForeignKey, UniqueConstraint, DateTime
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

    study_scores = relationship(
        "StudyScore",
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
    actual_updated_at = Column(DateTime(timezone=True), nullable=True)
    predicted_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="study_scores")

    __table_args__ = (
        UniqueConstraint("user_id", "subject", "grade_level", "semester", name="uq_user_subject_grade_semester"),
    )
