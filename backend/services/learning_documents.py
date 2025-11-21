from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from core.study_constants import GRADE_DISPLAY, SEMESTER_DISPLAY
from db import models
from services.vector_store import VectorItem, VectorStore

SCORE_REFERENCE_TYPE = "study_score"


def _score_document_title(score: models.StudyScore) -> str:
    grade_label = GRADE_DISPLAY.get(score.grade_level, score.grade_level)
    semester_label = SEMESTER_DISPLAY.get(score.semester, score.semester)
    return f"Điểm {score.subject} - {grade_label} ({semester_label})"


def _score_document_content(score: models.StudyScore) -> str:
    parts: List[str] = [
        f"Học sinh ID: {score.user_id}",
        f"Môn học: {score.subject}",
        f"Khối lớp: {GRADE_DISPLAY.get(score.grade_level, score.grade_level)}",
        f"Học kỳ: {SEMESTER_DISPLAY.get(score.semester, score.semester)}",
    ]
    if score.actual_score is not None:
        parts.append(f"Điểm thực tế: {score.actual_score:.2f}")
        if score.actual_source:
            parts.append(f"Nguồn điểm thực tế: {score.actual_source}")
        if score.actual_status:
            parts.append(f"Trạng thái điểm thực tế: {score.actual_status}")
        if score.actual_updated_at:
            parts.append(f"Thời gian cập nhật thực tế: {score.actual_updated_at.isoformat()}")
    if score.predicted_score is not None:
        parts.append(f"Điểm dự đoán: {score.predicted_score:.2f}")
        if score.predicted_source:
            parts.append(f"Nguồn điểm dự đoán: {score.predicted_source}")
        if score.predicted_status:
            parts.append(f"Trạng thái dự đoán: {score.predicted_status}")
        if score.predicted_updated_at:
            parts.append(f"Thời gian cập nhật dự đoán: {score.predicted_updated_at.isoformat()}")
    parts.append(f"Cập nhật lần cuối: {score.updated_at.isoformat() if score.updated_at else datetime.utcnow().isoformat()}")
    return "\n".join(parts)


def upsert_score_document(db: Session, score: models.StudyScore) -> models.LearningDocument:
    document = (
        db.query(models.LearningDocument)
        .filter(
            models.LearningDocument.reference_type == SCORE_REFERENCE_TYPE,
            models.LearningDocument.reference_id == score.id,
        )
        .first()
    )

    if not document:
        document = models.LearningDocument(
            user_id=score.user_id,
            source=SCORE_REFERENCE_TYPE,
            reference_type=SCORE_REFERENCE_TYPE,
            reference_id=score.id,
        )
        db.add(document)

    document.title = _score_document_title(score)
    document.content = _score_document_content(score)
    document.metadata_ = {
        "user_id": score.user_id,
        "subject": score.subject,
        "grade_level": score.grade_level,
        "semester": score.semester,
        "actual_score": score.actual_score,
        "predicted_score": score.predicted_score,
        "actual_source": score.actual_source,
        "predicted_source": score.predicted_source,
        "actual_status": score.actual_status,
        "predicted_status": score.predicted_status,
    }
    return document


def remove_score_document(db: Session, score_id: int) -> Optional[List[str]]:
    document = (
        db.query(models.LearningDocument)
        .filter(
            models.LearningDocument.reference_type == SCORE_REFERENCE_TYPE,
            models.LearningDocument.reference_id == score_id,
        )
        .first()
    )
    if not document:
        return None

    vector_ids = [embedding.vector_id for embedding in document.embeddings]

    db.delete(document)
    return vector_ids if vector_ids else None


def sync_score_embeddings(
    db: Session,
    vector_store: VectorStore,
    scores: Iterable[models.StudyScore],
) -> None:
    documents: List[models.LearningDocument] = []
    items: List[VectorItem] = []

    for score in scores:
        document = upsert_score_document(db, score)
        documents.append(document)

    db.flush()

    contents = [doc.content for doc in documents]
    if not contents:
        return

    embeddings = vector_store.encode(contents)

    for document, vector, content in zip(documents, embeddings, contents, strict=True):
        vector_id = f"score-{document.reference_id}"
        metadata = dict(document.metadata_ or {})
        metadata.update(
            {
                "document_id": document.id,
                "user_id": document.user_id,
                "title": document.title,
                "source": document.source,
            }
        )
        items.append(VectorItem(vector_id=vector_id, content=content, metadata=metadata))

        embedding_record = (
            db.query(models.KnowledgeEmbedding)
            .filter(models.KnowledgeEmbedding.document_id == document.id)
            .first()
        )
        if not embedding_record:
            embedding_record = models.KnowledgeEmbedding(
                document_id=document.id,
                vector_id=vector_id,
                model=vector_store.model_name,
                dimension=int(vector.shape[0]),
                metadata_={"source": document.source},
            )
            db.add(embedding_record)
        else:
            embedding_record.vector_id = vector_id
            embedding_record.model = vector_store.model_name
            embedding_record.dimension = int(vector.shape[0])
            existing_meta = embedding_record.metadata_ or {}
            existing_meta.update({"source": document.source})
            embedding_record.metadata_ = existing_meta

    vector_store.upsert(items, embeddings=embeddings)


def rebuild_all_score_embeddings(db: Session, vector_store: VectorStore) -> None:
    scores = db.query(models.StudyScore).all()
    vector_store.reset()
    if not scores:
        return
    db.flush()
    sync_score_embeddings(db, vector_store, scores)

