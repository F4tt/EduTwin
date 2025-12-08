from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, File, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from db import database, models
from services import document_extractor
from services.llm_provider import get_llm_provider
from utils.session_utils import get_current_user, require_auth

router = APIRouter(prefix="/developer", tags=["Developer"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_developer(user: dict | None) -> None:
    if not user or user.get("role") not in {"developer", "admin"}:
        raise HTTPException(status_code=403, detail="Chỉ developer mới được phép truy cập tính năng này.")


def _retrigger_pipeline_for_all_users(db: Session) -> dict:
    """Retrigger ML pipeline for all users with active structures after model/parameter changes."""
    from api.custom_model import _trigger_prediction_for_structure
    
    # Get active structure
    active_structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if not active_structure:
        return {"success": False, "message": "No active structure", "users_processed": 0}
    
    # Get all users with scores in this structure
    user_ids = db.query(models.CustomUserScore.user_id).filter(
        models.CustomUserScore.structure_id == active_structure.id,
        models.CustomUserScore.actual_score.isnot(None)
    ).distinct().all()
    
    users_processed = 0
    users_failed = 0
    
    for (user_id,) in user_ids:
        try:
            result = _trigger_prediction_for_structure(db, user_id, active_structure.id)
            if result["success"]:
                users_processed += 1
            else:
                users_failed += 1
        except Exception as e:
            print(f"[RETRIGGER] Failed for user {user_id}: {str(e)}")
            users_failed += 1
    
    return {
        "success": True,
        "users_processed": users_processed,
        "users_failed": users_failed,
        "structure_id": active_structure.id
    }


@router.post("/llm-test")
async def llm_test(payload: dict = Body(...)):
    """Test LLM connectivity."""
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' in request body.")

    provider = get_llm_provider()
    system = {
        "role": "system",
        "content": "Bạn là trợ lý. Trả lời ngắn gọn, bằng tiếng Việt."
    }
    user_msg = {"role": "user", "content": message}
    
    try:
        resp = await provider.chat(messages=[system, user_msg], temperature=0.2)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")

    def _scan(obj):
        if isinstance(obj, str) and len(obj) > 5:
            return obj
        if isinstance(obj, dict):
            for v in obj.values():
                res = _scan(v)
                if res:
                    return res
        if isinstance(obj, list):
            for v in obj:
                res = _scan(v)
                if res:
                    return res
        return None

    answer = None
    if isinstance(resp, dict):
        choices = resp.get("choices")
        if isinstance(choices, list) and choices:
            c0 = choices[0]
            if isinstance(c0, dict):
                msg = c0.get("message") or {}
                answer = msg.get("content") if isinstance(msg, dict) else None
                if not answer and isinstance(c0.get("text"), str):
                    answer = c0.get("text")
        if not answer:
            out = resp.get("outputs") or resp.get("predictions") or resp.get("candidates")
            ans = _scan(out) if out else None
            if ans:
                answer = ans
        if not answer:
            answer = _scan(resp)

    return JSONResponse(content={"raw": resp, "answer": answer})


@router.get("/dataset-status")
@require_auth
def get_dataset_status(request: Request, db: Session = Depends(get_db)):
    """Get ML reference dataset status."""
    user = get_current_user(request)
    _ensure_developer(user)

    sample_count = db.query(models.MLReferenceDataset).count()
    
    all_imports = (
        db.query(models.DataImportLog)
        .order_by(models.DataImportLog.created_at.desc())
        .all()
    )
    
    last_import = None
    for imp in all_imports:
        if imp.metadata_:
            metadata = imp.metadata_ if isinstance(imp.metadata_, dict) else {}
            if metadata.get('dataset_type') == 'ml_reference':
                last_import = imp
                break
    
    if not last_import and all_imports:
        last_import = all_imports[0]
    
    if sample_count > 0:
        sample = db.query(models.MLReferenceDataset).first()
        if sample and sample.feature_data:
            avg_features = len(sample.feature_data)
            estimated_bytes = sample_count * avg_features * 20
            size_mb = estimated_bytes / (1024 * 1024)
        else:
            size_mb = 0
    else:
        size_mb = 0

    result = {
        "has_dataset": sample_count > 0,
        "sample_count": sample_count,
        "size_mb": round(size_mb, 2),
        "last_import": None
    }

    if last_import:
        result["last_import"] = {
            "filename": last_import.filename,
            "imported_rows": last_import.imported_rows,
            "total_rows": last_import.total_rows,
            "skipped_rows": last_import.skipped_rows,
            "created_at": last_import.created_at.isoformat() if last_import.created_at else None,
            "uploaded_by": last_import.uploaded_by
        }

    return result


# ===== CUSTOM STRUCTURE DOCUMENT MANAGEMENT =====

@router.post("/structure-documents/upload")
@require_auth
async def upload_structure_document(
    request: Request,
    structure_id: int = Body(...),
    file: bytes = File(...),
    file_name: str = Body(...),
    file_type: str = Body(...),
    db: Session = Depends(get_db)
):
    """Upload a reference document for a custom teaching structure."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    _ensure_developer(user)
    
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu trúc giảng dạy")
    
    allowed_types = ['pdf', 'docx', 'doc', 'txt']
    clean_file_type = file_type.lower().replace('.', '')
    if clean_file_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file không hợp lệ. Chỉ hỗ trợ: {', '.join(allowed_types)}"
        )
    
    try:
        original_content, extracted_summary, metadata = await document_extractor.process_uploaded_document(
            file_bytes=file,
            file_name=file_name,
            file_type=clean_file_type,
            structure_name=structure.structure_name
        )
        
        new_doc = models.CustomStructureDocument(
            structure_id=structure_id,
            file_name=file_name,
            file_type=clean_file_type,
            file_size=len(file),
            original_content=original_content,
            extracted_summary=extracted_summary,
            extraction_method=metadata.get('extraction_method', 'llm_summary'),
            metadata_=metadata,
            uploaded_by=user.get("user_id")
        )
        
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)
        
        return JSONResponse(content={
            "message": "Tải tài liệu thành công",
            "document": {
                "id": new_doc.id,
                "file_name": new_doc.file_name,
                "file_type": new_doc.file_type,
                "file_size": new_doc.file_size,
                "summary_length": len(extracted_summary),
                "compression_ratio": metadata.get('compression_ratio', 0),
                "created_at": new_doc.created_at.isoformat() if new_doc.created_at else None
            }
        })
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý tài liệu: {str(e)}")


@router.get("/structure-documents/{structure_id}")
@require_auth
async def get_structure_documents(
    request: Request,
    structure_id: int,
    db: Session = Depends(get_db)
):
    """Get all reference documents for a structure."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    _ensure_developer(user)
    
    documents = db.query(models.CustomStructureDocument).filter(
        models.CustomStructureDocument.structure_id == structure_id
    ).order_by(models.CustomStructureDocument.created_at.desc()).all()
    
    return JSONResponse(content={
        "documents": [
            {
                "id": doc.id,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "summary_length": len(doc.extracted_summary) if doc.extracted_summary else 0,
                "compression_ratio": doc.metadata_.get('compression_ratio', 0) if doc.metadata_ else 0,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "summary_preview": doc.extracted_summary[:200] + "..." if doc.extracted_summary and len(doc.extracted_summary) > 200 else doc.extracted_summary
            }
            for doc in documents
        ]
    })


@router.delete("/structure-documents/{doc_id}")
@require_auth
async def delete_structure_document(
    request: Request,
    doc_id: int,
    db: Session = Depends(get_db)
):
    """Delete a reference document."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    _ensure_developer(user)
    
    document = db.query(models.CustomStructureDocument).filter(
        models.CustomStructureDocument.id == doc_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    try:
        db.delete(document)
        db.commit()
        
        return JSONResponse(content={"message": "Đã xóa tài liệu thành công"})
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa tài liệu: {str(e)}")


@router.get("/structure-documents/{doc_id}/full")
@require_auth
async def get_document_full_content(
    request: Request,
    doc_id: int,
    db: Session = Depends(get_db)
):
    """Get full content of a document."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    _ensure_developer(user)
    
    document = db.query(models.CustomStructureDocument).filter(
        models.CustomStructureDocument.id == doc_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    
    return JSONResponse(content={
        "id": document.id,
        "file_name": document.file_name,
        "file_type": document.file_type,
        "original_content": document.original_content,
        "extracted_summary": document.extracted_summary,
        "metadata": document.metadata_
    })


# ========== ML Model Management Endpoints ==========
# Note: These manage global ML settings (not per-structure)

@router.get("/model-status")
@require_auth
def get_model_status(request: Request, db: Session = Depends(get_db)):
    """Get current ML model status and configuration."""
    user = get_current_user(request)
    _ensure_developer(user)
    
    # Get active model from database
    config = db.query(models.MLModelConfig).first()
    if not config:
        # Create default config if not exists
        config = models.MLModelConfig(id=1, active_model="knn")
        db.add(config)
        db.commit()
        db.refresh(config)
    
    return JSONResponse(content={
        "active_model": config.active_model,
        "available_models": ["knn", "kernel_regression", "lwlr"],
        "message": f"Mô hình {config.active_model.upper()} đang được sử dụng"
    })


@router.get("/model-parameters")
@require_auth
def get_model_parameters(request: Request, db: Session = Depends(get_db)):
    """Get ML model parameters."""
    user = get_current_user(request)
    _ensure_developer(user)
    
    # Get parameters from database
    params = db.query(models.ModelParameters).first()
    if not params:
        # Create default parameters if not exists
        params = models.ModelParameters(id=1, knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
        db.add(params)
        db.commit()
        db.refresh(params)
    
    return JSONResponse(content={
        "knn_n": params.knn_n,
        "kr_bandwidth": params.kr_bandwidth,
        "lwlr_tau": params.lwlr_tau
    })


@router.post("/model-parameters")
@require_auth
async def update_model_parameters(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Update ML model parameters."""
    user = get_current_user(request)
    _ensure_developer(user)
    
    # Get or create parameters
    params = db.query(models.ModelParameters).first()
    if not params:
        params = models.ModelParameters(id=1)
        db.add(params)
    
    # Update parameters
    if "knn_n" in payload:
        params.knn_n = int(payload["knn_n"])
    if "kr_bandwidth" in payload:
        params.kr_bandwidth = float(payload["kr_bandwidth"])
    if "lwlr_tau" in payload:
        params.lwlr_tau = float(payload["lwlr_tau"])
    
    params.updated_by = user.id
    params.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(params)
    
    # Retrigger pipeline for all users
    retrigger_result = _retrigger_pipeline_for_all_users(db)
    
    return JSONResponse(content={
        "message": "Thông số mô hình đã được cập nhật",
        "knn_n": params.knn_n,
        "kr_bandwidth": params.kr_bandwidth,
        "lwlr_tau": params.lwlr_tau,
        "pipeline_retrigger": retrigger_result
    })


@router.post("/select-model")
@require_auth
async def select_model(
    request: Request,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Select active ML model."""
    user = get_current_user(request)
    _ensure_developer(user)
    
    model_name = payload.get("model", "").strip()
    valid_models = ["knn", "kernel_regression", "lwlr"]
    
    if model_name not in valid_models:
        raise HTTPException(status_code=400, detail=f"Mô hình không hợp lệ. Chọn từ: {', '.join(valid_models)}")
    
    # Get or create model config
    config = db.query(models.MLModelConfig).first()
    if not config:
        config = models.MLModelConfig(id=1, active_model="knn")
        db.add(config)
    
    # Update active model
    config.active_model = model_name
    config.updated_by = user.id
    config.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(config)
    
    # Retrigger pipeline for all users
    retrigger_result = _retrigger_pipeline_for_all_users(db)
    
    return JSONResponse(content={
        "message": f"Đã chuyển sang mô hình {model_name.upper()}",
        "active_model": config.active_model,
        "pipeline_retrigger": retrigger_result
    })




