from __future__ import annotations

import time
from dataclasses import asdict
from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, HTTPException, Request, Body, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from db import database, models
from ml import prediction_service
from services import excel_importer, model_evaluator
# REMOVED: learning_documents and vector_store_provider imports (no longer used)
from services.llm_provider import get_llm_provider
from services.ml_version_manager import increment_ml_version, mark_all_users_for_update, get_current_ml_version
from utils.session_utils import SessionManager, get_current_user, require_auth

router = APIRouter(prefix="/developer", tags=["Developer"])


class SelectModelRequest(BaseModel):
    model: str


class UpdateParametersRequest(BaseModel):
    knn_n: int
    kr_bandwidth: float
    lwlr_tau: float


class ParametersResponse(BaseModel):
    knn_n: int
    kr_bandwidth: float
    lwlr_tau: float
    updated_at: str | None = None


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_developer(user: dict | None) -> None:
    # Allow developer, admin, or institution to access these tools
    if not user:
        raise HTTPException(status_code=403, detail="Yêu cầu đăng nhập để truy cập tính năng này.")
    
    user_type = user.get("user_type")
    role = user.get("role")
    
    # Allow institutions (user_type="institution") or developer/admin roles
    if user_type == "institution" or role in {"developer", "admin"}:
        return
    
    raise HTTPException(status_code=403, detail="Chỉ developer hoặc cơ sở giáo dục mới được phép truy cập tính năng này.")


def _run_prediction_pipeline(db: Session) -> dict:
    """Recompute predictions for every user (vector sync removed)."""
    start = time.perf_counter()
    user_ids = [row[0] for row in db.query(models.User.id).all()]
    scores_to_sync = []

    try:
        for user_id in user_ids:
            updates = prediction_service.update_predictions_for_user(db, user_id)
            if updates:
                scores_to_sync.extend(updates)

        # REMOVED: Vector store sync (not needed for score analytics)
        # if scores_to_sync:
        #     db.flush()
        #     learning_documents.sync_score_embeddings(db, vector_store, scores_to_sync)

        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi pipeline ML: {exc}")

    duration = round(time.perf_counter() - start, 2)
    return {
        "processed_users": len(user_ids),
        "synced_scores": len(scores_to_sync),
        "duration_seconds": duration,
    }


def _run_prediction_pipeline_background():
    """Background task to run prediction pipeline for all users."""
    db = database.SessionLocal()
    try:
        print("[PIPELINE] Starting background prediction pipeline for all users...")
        start = time.perf_counter()
        user_ids = [row[0] for row in db.query(models.User.id).all()]
        scores_to_sync = []

        for user_id in user_ids:
            try:
                updates = prediction_service.update_predictions_for_user(db, user_id)
                if updates:
                    scores_to_sync.extend(updates)
            except Exception as e:
                print(f"[PIPELINE] Error processing user {user_id}: {e}")
                continue

        # REMOVED: Vector store sync (not needed for score analytics)
        # if scores_to_sync:
        #     db.flush()
        #     learning_documents.sync_score_embeddings(db, vector_store, scores_to_sync)

        db.commit()
        duration = round(time.perf_counter() - start, 2)
        print(f"[PIPELINE] Completed: {len(user_ids)} users, {len(scores_to_sync)} scores synced in {duration}s")
    except Exception as exc:
        print(f"[PIPELINE] Error in background pipeline: {exc}")
        db.rollback()
    finally:
        db.close()


@router.post("/import-excel")
@require_auth
async def import_excel_data(
    request: Request,
    db: Session = Depends(get_db),
    file = File(...),
):
    user = get_current_user(request)
    _ensure_developer(user)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="File rỗng.")

    # Get institution_id if user is institution
    institution_id = user.get("institution_id") if user.get("user_type") == "institution" else None
    
    summary = excel_importer.import_knn_reference_dataset(
        db,
        file_bytes=contents,
        filename=file.filename or "knn_reference.xlsx",
        uploader_id=user.get("user_id") or user.get("institution_id"),
        institution_id=institution_id,
    )

    # Mark all users for update (dataset changed)
    mark_all_users_for_update(db)
    increment_ml_version(db, 'both')  # Dataset change affects both model and params
    current_version = get_current_ml_version(db)

    return JSONResponse(content={
        "summary": asdict(summary),
        "ml_version": current_version,
        "note": "Dữ liệu đã được import. Predictions sẽ được cập nhật khi user truy cập."
    })


# REMOVED: /rebuild-embeddings endpoint (vector store no longer used)


@router.post("/llm-test")
async def llm_test(payload: dict = Body(...)):
    """Temporary unauthenticated endpoint for quickly testing LLM connectivity.
    WARNING: This endpoint is for local development only. It should be removed or guarded in production.
    """
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' in request body.")

    provider = get_llm_provider()

    # build a minimal system + user message list
    system = {
        "role": "system",
        "content": "Bạn là trợ lý. Trả lời ngắn gọn, bằng tiếng Việt. Đây là kiểm tra kết nối LLM."
    }
    user = {"role": "user", "content": message}
    try:
        resp = await provider.chat(messages=[system, user], temperature=0.2)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}")

    # best-effort extraction of first reasonable text
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
        # try common places
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
    """Get current dataset status: count, size, last import time. Only for developer/admin/institution."""
    try:
        user = get_current_user(request)
        _ensure_developer(user)

        # Get institution_id if user is institution, otherwise None for global data
        institution_id = user.get("institution_id") if user.get("user_type") == "institution" else None

        # Count reference samples (filtered by institution or global)
        if institution_id:
            sample_count = db.query(models.KNNReferenceSample).filter(
                models.KNNReferenceSample.institution_id == institution_id
            ).count()
        else:
            sample_count = db.query(models.KNNReferenceSample).filter(
                (models.KNNReferenceSample.institution_id == None) | 
                (models.KNNReferenceSample.institution_id.is_(None))
            ).count()
        
        # Get last import log for KNN reference dataset (filtered by institution)
        # Try to find imports with dataset_type = 'knn_reference' in metadata
        import_query = db.query(models.DataImportLog)
        
        # Filter by institution_id
        if institution_id:
            import_query = import_query.filter(
                models.DataImportLog.institution_id == institution_id
            )
        else:
            import_query = import_query.filter(
                models.DataImportLog.institution_id.is_(None)
            )
        
        all_imports = import_query.order_by(models.DataImportLog.created_at.desc()).all()
        
        last_import = None
        for imp in all_imports:
            if imp.metadata_:
                metadata = imp.metadata_ if isinstance(imp.metadata_, dict) else {}
                if metadata.get('dataset_type') == 'knn_reference':
                    last_import = imp
                    break
        
        # If no specific KNN import found, use the most recent import
        if not last_import and all_imports:
            last_import = all_imports[0]
        
        # Calculate dataset size (approximate)
        if sample_count > 0:
            # Get a sample to estimate size per record (filtered by institution)
            if institution_id:
                sample = db.query(models.KNNReferenceSample).filter(
                    models.KNNReferenceSample.institution_id == institution_id
                ).first()
            else:
                sample = db.query(models.KNNReferenceSample).filter(
                    models.KNNReferenceSample.institution_id.is_(None)
                ).first()
            
            if sample and sample.feature_data:
                avg_features = len(sample.feature_data)
                # Rough estimate: each feature is ~8 bytes (float) + key overhead
                estimated_bytes = sample_count * avg_features * 20  # rough estimate
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy trạng thái dataset: {str(e)}")


@router.get("/model-parameters", response_model=ParametersResponse)
@require_auth
def get_model_parameters(request: Request, db: Session = Depends(get_db)):
    """Get current model parameters (KNN n, KR bandwidth, LWLR tau). Only for developer/admin/institution."""
    try:
        user = get_current_user(request)
        _ensure_developer(user)

        institution_id = user.get("institution_id") if user.get("user_type") == "institution" else None

        if institution_id:
            # Get institution-specific parameters
            params = db.query(models.InstitutionModelParameters).filter(
                models.InstitutionModelParameters.institution_id == institution_id
            ).first()
            if not params:
                try:
                    # Create defaults for this institution
                    params = models.InstitutionModelParameters(
                        institution_id=institution_id,
                        knn_n=15,
                        kr_bandwidth=1.25,
                        lwlr_tau=3.0,
                        active_model='knn'
                    )
                    db.add(params)
                    db.commit()
                    db.refresh(params)
                except Exception as e:
                    db.rollback()
                    # Check if record was created by another request (race condition)
                    params = db.query(models.InstitutionModelParameters).filter(
                        models.InstitutionModelParameters.institution_id == institution_id
                    ).first()
                    if not params:
                        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo thông số mô hình: {str(e)}")
        else:
            # Get global parameters
            params = db.query(models.ModelParameters).first()
            if not params:
                try:
                    # Create with defaults
                    params = models.ModelParameters(knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
                    db.add(params)
                    db.commit()
                    db.refresh(params)
                except Exception as e:
                    db.rollback()
                    params = db.query(models.ModelParameters).first()
                    if not params:
                        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo thông số mô hình: {str(e)}")

        return ParametersResponse(
            knn_n=params.knn_n,
            kr_bandwidth=params.kr_bandwidth,
            lwlr_tau=params.lwlr_tau,
            updated_at=params.updated_at.isoformat() if params.updated_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy thông số mô hình: {str(e)}")


@router.post("/model-parameters")
async def update_model_parameters(background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    """Update model parameters. Only for developer/admin."""
    # Handle auth manually
    session_id = request.cookies.get('session_id')
    if not session_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    user = SessionManager.get_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Session không hợp lệ")
    
    _ensure_developer(user)

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body phải là JSON hợp lệ")
    
    # Validate parameters exist
    if not payload or not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body không hợp lệ")
    
    # Extract and validate each parameter
    try:
        knn_n = int(payload.get("knn_n", 15))
        kr_bandwidth = float(payload.get("kr_bandwidth", 1.25))
        lwlr_tau = float(payload.get("lwlr_tau", 3.0))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Các thông số phải có kiểu dữ liệu hợp lệ")
    
    # Validate ranges
    if knn_n < 1 or knn_n > 100:
        raise HTTPException(status_code=400, detail="KNN n phải trong khoảng 1-100")
    if kr_bandwidth < 0.1 or kr_bandwidth > 10.0:
        raise HTTPException(status_code=400, detail="Kernel Regression bandwidth phải trong khoảng 0.1-10.0")
    if lwlr_tau < 0.5 or lwlr_tau > 10.0:
        raise HTTPException(status_code=400, detail="LWLR tau phải trong khoảng 0.5-10.0")

    try:
        institution_id = user.get("institution_id") if user.get("user_type") == "institution" else None

        if institution_id:
            # Update institution-specific parameters
            params = db.query(models.InstitutionModelParameters).filter(
                models.InstitutionModelParameters.institution_id == institution_id
            ).first()
            if not params:
                params = models.InstitutionModelParameters(
                    institution_id=institution_id,
                    knn_n=knn_n,
                    kr_bandwidth=kr_bandwidth,
                    lwlr_tau=lwlr_tau,
                    active_model='knn'
                )
                db.add(params)
            else:
                params.knn_n = knn_n
                params.kr_bandwidth = kr_bandwidth
                params.lwlr_tau = lwlr_tau
                from datetime import datetime
                params.updated_at = datetime.utcnow()
        else:
            # Update global parameters
            params = db.query(models.ModelParameters).first()
            if not params:
                params = models.ModelParameters()
                db.add(params)

            params.knn_n = knn_n
            params.kr_bandwidth = kr_bandwidth
            params.lwlr_tau = lwlr_tau
            params.updated_by = user.get("user_id")

        db.commit()
        db.refresh(params)

        # Increment version to mark that predictions need update
        increment_ml_version(db, 'params')
        current_version = get_current_ml_version(db)

        return JSONResponse(content={
            "message": "Đã cập nhật thông số mô hình thành công",
            "knn_n": params.knn_n,
            "kr_bandwidth": params.kr_bandwidth,
            "lwlr_tau": params.lwlr_tau,
            "ml_version": current_version,
            "note": "Dự đoán sẽ được cập nhật khi user truy cập dữ liệu."
        })
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi cơ sở dữ liệu: {str(e)}")


@router.get("/model-status")
@require_auth
def get_model_status(request: Request, db: Session = Depends(get_db)):
    """Get current active ML model and available options. Only for developer/admin/institution."""
    try:
        user = get_current_user(request)
        _ensure_developer(user)

        institution_id = user.get("institution_id") if user.get("user_type") == "institution" else None

        if institution_id:
            # Get institution-specific model config
            config = db.query(models.InstitutionModelParameters).filter(
                models.InstitutionModelParameters.institution_id == institution_id
            ).first()
            if not config:
                try:
                    config = models.InstitutionModelParameters(
                        institution_id=institution_id,
                        knn_n=15,
                        kr_bandwidth=1.25,
                        lwlr_tau=3.0,
                        active_model="knn"
                    )
                    db.add(config)
                    db.commit()
                    db.refresh(config)
                except Exception as e:
                    db.rollback()
                    # Check if record was created by another request (race condition)
                    config = db.query(models.InstitutionModelParameters).filter(
                        models.InstitutionModelParameters.institution_id == institution_id
                    ).first()
                    if not config:
                        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo cấu hình mô hình: {str(e)}")
            active_model = config.active_model
        else:
            # Get global model config
            config = db.query(models.MLModelConfig).first()
            if not config:
                try:
                    config = models.MLModelConfig(active_model="knn")
                    db.add(config)
                    db.commit()
                    db.refresh(config)
                except Exception as e:
                    db.rollback()
                    config = db.query(models.MLModelConfig).first()
                    if not config:
                        raise HTTPException(status_code=500, detail=f"Không thể khởi tạo cấu hình mô hình: {str(e)}")
            active_model = config.active_model

        return {
            "active_model": active_model,
            "available_models": ["knn", "kernel_regression", "lwlr"],
            "descriptions": {
                "knn": "K-Nearest Neighbors (default, distance-weighted)",
                "kernel_regression": "Kernel Regression (Nadaraya-Watson)",
                "lwlr": "Locally Weighted Linear Regression"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lấy trạng thái mô hình: {str(e)}")


@router.post("/evaluate-models")
@require_auth
def evaluate_models(request: Request, db: Session = Depends(get_db)):
    """
    Evaluate all three ML models (KNN, Kernel Regression, LWLR) on two prediction tasks:
    1. Predict grade 12 from grades 10-11
    2. Predict grade 11 from grade 10
    
    Returns metrics (MAE, MSE, RMSE, Accuracy) for each model-task combination
    and a recommendation for the best model(s).
    
    Only for developer/admin.
    """
    try:
        user = get_current_user(request)
        _ensure_developer(user)

        # Run evaluation on shared dataset
        results = model_evaluator.evaluate_all_models(db)

        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi đánh giá mô hình: {str(e)}")


@router.post("/select-model")
async def select_model(background_tasks: BackgroundTasks, request: Request, db: Session = Depends(get_db)):
    """Switch to a different ML prediction model. Only for developer/admin."""
    # Handle auth manually
    session_id = request.cookies.get('session_id')
    if not session_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    user = SessionManager.get_session(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Session không hợp lệ")
    
    _ensure_developer(user)

    try:

        # Parse request body manually to handle validation errors better
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Request body phải là JSON hợp lệ")
        
        if not body or not isinstance(body, dict) or 'model' not in body:
            raise HTTPException(status_code=400, detail="Thiếu trường 'model' trong request body")
        
        model_name = str(body.get('model', '')).strip()
        if not model_name:
            raise HTTPException(status_code=400, detail="Trường 'model' không được để trống")

        allowed_models = ["knn", "kernel_regression", "lwlr"]
        if model_name not in allowed_models:
            raise HTTPException(status_code=400, detail=f"Mô hình không hợp lệ. Cho phép: {', '.join(allowed_models)}")

        institution_id = user.get("institution_id") if user.get("user_type") == "institution" else None

        if institution_id:
            # Update institution-specific model
            config = db.query(models.InstitutionModelParameters).filter(
                models.InstitutionModelParameters.institution_id == institution_id
            ).first()
            if not config:
                try:
                    config = models.InstitutionModelParameters(
                        institution_id=institution_id,
                        knn_n=15,
                        kr_bandwidth=1.25,
                        lwlr_tau=3.0,
                        active_model=model_name
                    )
                    db.add(config)
                    db.commit()
                    db.refresh(config)
                except Exception as e:
                    db.rollback()
                    # Check if record was created by another request (race condition)
                    config = db.query(models.InstitutionModelParameters).filter(
                        models.InstitutionModelParameters.institution_id == institution_id
                    ).first()
                    if not config:
                        raise HTTPException(status_code=500, detail=f"Không thể tạo cấu hình mô hình: {str(e)}")
            else:
                try:
                    config.active_model = model_name
                    from datetime import datetime
                    config.updated_at = datetime.utcnow()
                    db.commit()
                    db.refresh(config)
                except Exception as e:
                    db.rollback()
                    raise HTTPException(status_code=500, detail=f"Không thể cập nhật cấu hình mô hình: {str(e)}")
            active_model_value = config.active_model
        else:
            # Update global model config
            config = db.query(models.MLModelConfig).first()
            if not config:
                try:
                    config = models.MLModelConfig(active_model=model_name, updated_by=user.get("user_id"))
                    db.add(config)
                    db.commit()
                    db.refresh(config)
                except Exception as e:
                    db.rollback()
                    raise HTTPException(status_code=500, detail=f"Không thể tạo cấu hình mô hình: {str(e)}")
            else:
                try:
                    config.active_model = model_name
                    config.updated_by = user.get("user_id")
                    db.commit()
                    db.refresh(config)
                except Exception as e:
                    db.rollback()
                    raise HTTPException(status_code=500, detail=f"Không thể cập nhật cấu hình mô hình: {str(e)}")
            active_model_value = config.active_model

        # Increment version to mark that predictions need update
        increment_ml_version(db, 'model')
        current_version = get_current_ml_version(db)

        return JSONResponse(content={
            "message": f"Đã chuyển sang mô hình: {model_name}",
            "active_model": active_model_value,
            "ml_version": current_version,
            "note": "Dự đoán sẽ được cập nhật khi user truy cập dữ liệu."
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi chọn mô hình: {str(e)}")


# Teaching Structure endpoints
class TeachingStructureRequest(BaseModel):
    num_time_points: int
    num_subjects: int
    time_point_labels: list[str]
    subject_labels: list[str]


@router.get("/teaching-structure")
async def get_teaching_structure(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get teaching structure for current institution"""
    user = get_current_user(request)
    _ensure_developer(user)
    
    if user.get("user_type") != "institution":
        raise HTTPException(status_code=403, detail="Chỉ institution mới có thể truy cập cấu trúc giảng dạy")
    
    institution_id = user.get("institution_id")
    if not institution_id:
        raise HTTPException(status_code=400, detail="Không tìm thấy institution_id")
    
    structure = db.query(models.TeachingStructure).filter(
        models.TeachingStructure.institution_id == institution_id
    ).first()
    
    if not structure:
        return JSONResponse(content={"has_structure": False})
    
    return JSONResponse(content={
        "has_structure": True,
        "num_time_points": structure.num_time_points,
        "num_subjects": structure.num_subjects,
        "time_point_labels": structure.time_point_labels,
        "subject_labels": structure.subject_labels,
        "updated_at": structure.updated_at.isoformat() if structure.updated_at else None
    })


@router.post("/teaching-structure")
async def save_teaching_structure(
    request: Request,
    data: TeachingStructureRequest,
    db: Session = Depends(get_db)
):
    """Save or update teaching structure for current institution"""
    user = get_current_user(request)
    _ensure_developer(user)
    
    if user.get("user_type") != "institution":
        raise HTTPException(status_code=403, detail="Chỉ institution mới có thể lưu cấu trúc giảng dạy")
    
    institution_id = user.get("institution_id")
    if not institution_id:
        raise HTTPException(status_code=400, detail="Không tìm thấy institution_id")
    
    # Validate
    if data.num_time_points != len(data.time_point_labels):
        raise HTTPException(status_code=400, detail="Số lượng mốc thời gian không khớp với số labels")
    if data.num_subjects != len(data.subject_labels):
        raise HTTPException(status_code=400, detail="Số lượng môn học không khớp với số labels")
    
    # Check if structure exists
    structure = db.query(models.TeachingStructure).filter(
        models.TeachingStructure.institution_id == institution_id
    ).first()
    
    if structure:
        # Update existing
        structure.num_time_points = data.num_time_points
        structure.num_subjects = data.num_subjects
        structure.time_point_labels = data.time_point_labels
        structure.subject_labels = data.subject_labels
        message = "Đã cập nhật cấu trúc giảng dạy"
    else:
        # Create new
        structure = models.TeachingStructure(
            institution_id=institution_id,
            num_time_points=data.num_time_points,
            num_subjects=data.num_subjects,
            time_point_labels=data.time_point_labels,
            subject_labels=data.subject_labels
        )
        db.add(structure)
        message = "Đã lưu cấu trúc giảng dạy"
    
    db.commit()
    db.refresh(structure)
    
    return JSONResponse(content={
        "message": message,
        "structure": {
            "num_time_points": structure.num_time_points,
            "num_subjects": structure.num_subjects,
            "time_point_labels": structure.time_point_labels,
            "subject_labels": structure.subject_labels,
            "updated_at": structure.updated_at.isoformat()
        }
    })


# Pipeline toggle endpoint
class PipelineToggleRequest(BaseModel):
    enabled: bool


@router.post("/pipeline-toggle")
async def toggle_pipeline(
    request: Request,
    data: PipelineToggleRequest,
    db: Session = Depends(get_db)
):
    """Toggle pipeline enabled/disabled for current institution"""
    user = get_current_user(request)
    _ensure_developer(user)
    
    if user.get("user_type") == "institution":
        institution_id = user.get("institution_id")
        if not institution_id:
            raise HTTPException(status_code=400, detail="Không tìm thấy institution_id")
        
        # Get or create institution model parameters
        params = db.query(models.InstitutionModelParameters).filter(
            models.InstitutionModelParameters.institution_id == institution_id
        ).first()
        
        if not params:
            params = models.InstitutionModelParameters(
                institution_id=institution_id,
                pipeline_enabled=data.enabled
            )
            db.add(params)
        else:
            params.pipeline_enabled = data.enabled
        
        db.commit()
        db.refresh(params)
        
        return JSONResponse(content={
            "message": f"Pipeline đã được {'bật' if data.enabled else 'tắt'}",
            "pipeline_enabled": params.pipeline_enabled
        })
    else:
        # For global admin/developer - not supported yet
        raise HTTPException(status_code=403, detail="Tính năng này chỉ dành cho institution")


@router.get("/pipeline-status")
async def get_pipeline_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get pipeline status for current institution"""
    user = get_current_user(request)
    _ensure_developer(user)
    
    if user.get("user_type") == "institution":
        institution_id = user.get("institution_id")
        if not institution_id:
            raise HTTPException(status_code=400, detail="Không tìm thấy institution_id")
        
        params = db.query(models.InstitutionModelParameters).filter(
            models.InstitutionModelParameters.institution_id == institution_id
        ).first()
        
        if not params:
            return JSONResponse(content={"pipeline_enabled": True})  # Default enabled
        
        return JSONResponse(content={"pipeline_enabled": params.pipeline_enabled})
    else:
        # For global admin/developer
        return JSONResponse(content={"pipeline_enabled": True})


