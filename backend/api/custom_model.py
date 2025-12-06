"""
Custom Model API
Allows users to define custom teaching structures and upload custom datasets
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import pandas as pd
from io import BytesIO, StringIO
import json
from datetime import datetime

from db import database, models
from utils.session_utils import require_auth, get_current_user

router = APIRouter(prefix="/custom-model", tags=["CustomModel"])


def _trigger_prediction_for_structure(db: Session, user_id: int, structure_id: int) -> Dict:
    """
    Trigger ML prediction for a specific custom structure.
    Auto-enables pipeline if has both reference data AND user scores.
    Returns dict with prediction results or error info.
    """
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        return {"success": False, "message": "Structure not found"}
    
    # Check reference dataset exists
    reference_count = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).count()
    
    if reference_count == 0:
        return {"success": False, "message": "No reference dataset"}
    
    # Check user scores exist
    user_score_count = db.query(models.CustomUserScore).filter(
        models.CustomUserScore.user_id == user_id,
        models.CustomUserScore.structure_id == structure_id,
        models.CustomUserScore.actual_score.isnot(None)
    ).count()
    
    if user_score_count == 0:
        return {"success": False, "message": "No user scores"}
    
    # Auto-enable pipeline if has both reference data and user scores
    if not structure.pipeline_enabled:
        structure.pipeline_enabled = True
        db.commit()
        print(f"[AUTO-ENABLE] Pipeline enabled for structure {structure_id}")
    
    # Find current time point (latest with actual scores)
    time_points_with_data = set()
    for score in db.query(models.CustomUserScore).filter(
        models.CustomUserScore.user_id == user_id,
        models.CustomUserScore.structure_id == structure_id,
        models.CustomUserScore.actual_score.isnot(None)
    ).all():
        time_points_with_data.add(score.time_point)
    
    current_tp = None
    for tp in structure.time_point_labels:
        if tp in time_points_with_data:
            current_tp = tp
    
    if not current_tp:
        return {"success": False, "message": "No valid current time point"}
    
    # Run prediction
    try:
        model_config = db.query(models.MLModelConfig).first()
        active_model = model_config.active_model if model_config else "knn"
        
        model_params = db.query(models.ModelParameters).first()
        if not model_params:
            model_params = models.ModelParameters(knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
            db.add(model_params)
            db.commit()
            db.refresh(model_params)
        
        from ml.custom_prediction_service import update_predictions_for_custom_structure
        
        predicted_count = update_predictions_for_custom_structure(
            db=db,
            user_id=user_id,
            structure_id=structure_id,
            current_time_point=current_tp,
            active_model=active_model,
            model_params=model_params
        )
        
        return {
            "success": True,
            "predicted_count": predicted_count,
            "message": f"Đã dự đoán {predicted_count} điểm",
            "model_used": active_model
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Prediction failed: {str(e)}"
        }


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TeachingStructure(BaseModel):
    structure_name: str
    num_time_points: int
    num_subjects: int
    time_point_labels: List[str]
    subject_labels: List[str]

    @field_validator('structure_name')
    @classmethod
    def validate_structure_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Tên cấu trúc không được để trống")
        return v.strip()

    @field_validator('num_time_points', 'num_subjects')
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Phải lớn hơn 0")
        return v

    @field_validator('time_point_labels', 'subject_labels')
    @classmethod
    def validate_labels(cls, v: List[str]) -> List[str]:
        if any(not label.strip() for label in v):
            raise ValueError("Tất cả nhãn phải có giá trị")
        return v


class TogglePipelineRequest(BaseModel):
    enabled: bool


@router.get("/teaching-structure")
async def get_teaching_structure(
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get active teaching structure if exists"""
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id,
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if not structure:
        return {"has_structure": False}
    
    return {
        "has_structure": True,
        "structure_id": structure.id,
        "structure_name": structure.structure_name,
        "num_time_points": structure.num_time_points,
        "num_subjects": structure.num_subjects,
        "time_point_labels": structure.time_point_labels,
        "subject_labels": structure.subject_labels,
        "created_at": structure.created_at.isoformat() if structure.created_at else None
    }


@router.post("/update-current-time-point/{structure_id}")
async def update_current_time_point(
    structure_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Update current_time_point for a structure (similar to current_grade in StudyUpdate)
    """
    body = await request.json()
    current_time_point = body.get('current_time_point')
    
    print(f"[DEBUG] Updating current_time_point for structure {structure_id}, user {current_user.id}, value: {current_time_point}")
    
    if not current_time_point:
        raise HTTPException(status_code=400, detail="current_time_point is required")
    
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        print(f"[DEBUG] Structure {structure_id} not found for user {current_user.id}")
        raise HTTPException(status_code=404, detail="Structure not found")
    
    # Validate time point exists in structure
    if current_time_point not in structure.time_point_labels:
        print(f"[DEBUG] Invalid time point '{current_time_point}' for structure. Valid: {structure.time_point_labels}")
        raise HTTPException(status_code=400, detail="Invalid time point for this structure")
    
    print(f"[DEBUG] Before update: current_time_point = {structure.current_time_point}")
    structure.current_time_point = current_time_point
    db.commit()
    db.refresh(structure)
    print(f"[DEBUG] After update: current_time_point = {structure.current_time_point}")
    
    return {
        "success": True,
        "message": "Current time point updated successfully",
        "current_time_point": current_time_point
    }


@router.get("/teaching-structures")
async def get_all_teaching_structures(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all teaching structures for current user"""
    print(f"[DEBUG] Fetching structures for user_id: {current_user.id}")
    
    structures = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id
    ).order_by(models.CustomTeachingStructure.created_at.desc()).all()
    
    print(f"[DEBUG] Found {len(structures)} structures")
    
    result = {
        "structures": [
            {
                "id": s.id,
                "structure_name": s.structure_name,
                "num_time_points": s.num_time_points,
                "num_subjects": s.num_subjects,
                "time_point_labels": s.time_point_labels,
                "subject_labels": s.subject_labels,
                "current_time_point": s.current_time_point,
                "pipeline_enabled": s.pipeline_enabled,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in structures
        ]
    }
    
    print(f"[DEBUG] Returning structures: {[s['structure_name'] for s in result['structures']]}")
    return result


@router.post("/teaching-structure/activate/{structure_id}")
async def activate_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Activate a specific teaching structure"""
    # Verify structure belongs to user
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu trúc")
    
    # Deactivate all other structures
    db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id
    ).update({"is_active": False})
    
    # Activate selected structure
    structure.is_active = True
    db.commit()
    
    return {"message": f"Đã kích hoạt cấu trúc '{structure.structure_name}'"}


@router.delete("/teaching-structure/{structure_id}")
async def delete_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete a teaching structure"""
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu trúc")
    
    db.delete(structure)
    db.commit()
    
    return {"message": "Đã xóa cấu trúc thành công"}


@router.post("/teaching-structure")
async def save_teaching_structure(
    structure: TeachingStructure,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save new teaching structure (max 5 per user)"""
    # Validate that labels match counts
    if len(structure.time_point_labels) != structure.num_time_points:
        raise HTTPException(
            status_code=400,
            detail=f"Số lượng nhãn mốc thời gian ({len(structure.time_point_labels)}) không khớp với số lượng đã nhập ({structure.num_time_points})"
        )
    
    if len(structure.subject_labels) != structure.num_subjects:
        raise HTTPException(
            status_code=400,
            detail=f"Số lượng nhãn môn học ({len(structure.subject_labels)}) không khớp với số lượng đã nhập ({structure.num_subjects})"
        )
    
    # Check max limit (5 structures)
    count = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id
    ).count()
    
    if count >= 5:
        raise HTTPException(
            status_code=400,
            detail="Bạn đã đạt giới hạn tối đa 5 cấu trúc. Vui lòng xóa một cấu trúc cũ trước."
        )
    
    # Check for duplicate name
    duplicate = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id,
        models.CustomTeachingStructure.structure_name == structure.structure_name
    ).first()
    
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"Cấu trúc với tên '{structure.structure_name}' đã tồn tại"
        )
    
    # Deactivate all existing structures
    db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id
    ).update({"is_active": False})
    
    # Create new structure and set as active
    new_structure = models.CustomTeachingStructure(
        user_id=current_user.id,
        structure_name=structure.structure_name,
        num_time_points=structure.num_time_points,
        num_subjects=structure.num_subjects,
        time_point_labels=structure.time_point_labels,
        subject_labels=structure.subject_labels,
        is_active=True
    )
    db.add(new_structure)
    db.commit()
    db.refresh(new_structure)
    
    print(f"[DEBUG] Created structure: ID={new_structure.id}, Name={new_structure.structure_name}, User={current_user.id}")
    
    return {
        "message": "Cấu trúc giảng dạy đã được lưu thành công",
        "structure_id": new_structure.id
    }


@router.get("/pipeline-status")
async def get_pipeline_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get custom model pipeline status for active structure"""
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id,
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if not structure:
        return {"pipeline_enabled": False}
    
    return {"pipeline_enabled": structure.pipeline_enabled}


@router.post("/pipeline-toggle")
async def toggle_pipeline(
    request: TogglePipelineRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Toggle custom model pipeline on/off for active structure"""
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id,
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if not structure:
        raise HTTPException(
            status_code=404,
            detail="Chưa có cấu trúc giảng dạy được kích hoạt. Vui lòng chọn cấu trúc trước."
        )
    
    structure.pipeline_enabled = request.enabled
    structure.updated_at = datetime.utcnow()
    db.commit()
    
    status = "bật" if request.enabled else "tắt"
    message = f"Pipeline đã được {status} thành công"
    
    # Trigger prediction when enabling pipeline (if conditions met)
    if request.enabled:
        prediction_result = _trigger_prediction_for_structure(db, current_user.id, structure.id)
        if prediction_result["success"]:
            message += f" và {prediction_result['message']}"
    
    return {
        "pipeline_enabled": structure.pipeline_enabled,
        "message": message
    }


@router.post("/upload-dataset")
async def upload_custom_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Upload custom dataset for training to active structure"""
    # Check if active structure exists
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id,
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if not structure:
        raise HTTPException(
            status_code=404,
            detail="Chưa có cấu trúc giảng dạy được kích hoạt. Vui lòng chọn cấu trúc trước."
        )
    
    # Read file - Only accept Excel files
    try:
        contents = await file.read()
        
        # Only parse Excel files (reject CSV to avoid delimiter issues)
        if file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(BytesIO(contents))
        else:
            raise HTTPException(
                status_code=400,
                detail="Chỉ hỗ trợ file Excel (.xlsx, .xls). Vui lòng tải template Excel và điền dữ liệu."
            )
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Reset index after dropping rows
        df = df.reset_index(drop=True)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Không thể đọc file Excel: {str(e)}"
        )
    
    # Validate structure - only score columns required (no STT, no name)
    expected_score_columns = []
    
    for time_point in structure.time_point_labels:
        for subject in structure.subject_labels:
            expected_score_columns.append(f"{subject}_{time_point}")
    
    missing_columns = [col for col in expected_score_columns if col not in df.columns]
    
    if missing_columns:
        raise HTTPException(
            status_code=400,
            detail=f"File thiếu các cột điểm số: {', '.join(missing_columns)}"
        )
    
    # Clear existing custom dataset for this structure
    db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure.id
    ).delete()
    
    # Import data
    imported_count = 0
    skipped_rows = 0
    
    print(f"[UPLOAD] Processing {len(df)} rows from file")
    
    for idx, row in df.iterrows():
        # Extract score data
        score_data = {}
        valid_scores = 0
        
        for col in expected_score_columns:
            value = row[col]
            if pd.notna(value):
                try:
                    score_value = float(value)
                    # Validate score range (assuming reasonable values)
                    if score_value >= 0 and score_value < 100000:
                        score_data[col] = score_value
                        valid_scores += 1
                except (ValueError, TypeError):
                    continue
        
        # Only import rows with at least one valid score
        if valid_scores == 0:
            skipped_rows += 1
            continue
        
        # Create sample with auto-incrementing number (no STT column needed)
        sample = models.CustomDatasetSample(
            structure_id=structure.id,
            user_id=current_user.id,
            sample_name=f"Sample_{imported_count + 1}",
            score_data=score_data,
            metadata_={}
        )
        db.add(sample)
        imported_count += 1
    
    db.commit()
    
    print(f"[UPLOAD] Imported {imported_count} samples, skipped {skipped_rows} empty/invalid rows")
    
    # Trigger prediction for this structure only (if pipeline enabled and has user scores)
    prediction_result = _trigger_prediction_for_structure(db, current_user.id, structure.id)
    
    response = {
        "message": f"Đã import thành công {imported_count} mẫu dữ liệu",
        "imported_count": imported_count,
        "total_rows": len(df),
        "skipped_rows": skipped_rows
    }
    
    if prediction_result["success"]:
        response["message"] += f" và {prediction_result['message']}"
        response["auto_predicted"] = True
        response["predicted_count"] = prediction_result["predicted_count"]
    
    return response


@router.get("/dataset-stats")
async def get_dataset_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get statistics about uploaded custom dataset for active structure"""
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.user_id == current_user.id,
        models.CustomTeachingStructure.is_active == True
    ).first()
    
    if not structure:
        return {"has_structure": False, "sample_count": 0}
    
    sample_count = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure.id
    ).count()
    
    return {
        "has_structure": True,
        "sample_count": sample_count,
        "structure": {
            "structure_name": structure.structure_name,
            "num_time_points": structure.num_time_points,
            "num_subjects": structure.num_subjects,
            "time_point_labels": structure.time_point_labels,
            "subject_labels": structure.subject_labels
        }
    }


@router.get("/dataset-stats/{structure_id}")
async def get_dataset_stats_for_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get dataset statistics for a specific structure"""
    # Verify structure ownership
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")
    
    # Get reference dataset count
    reference_count = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).count()
    
    # Get latest upload timestamp
    latest_sample = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).order_by(models.CustomDatasetSample.created_at.desc()).first()
    
    return {
        "reference_count": reference_count,
        "last_upload": latest_sample.created_at.isoformat() if latest_sample else None
    }


@router.post("/user-scores")
async def save_user_scores(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save user's actual scores for custom structure"""
    body = await request.json()
    structure_id = body.get("structure_id")
    scores = body.get("scores", {})  # {subject_timepoint: score_value}
    
    if not structure_id:
        raise HTTPException(status_code=400, detail="structure_id is required")
    
    # Verify structure ownership
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")
    
    saved_count = 0
    
    for key, value in scores.items():
        if not key or value is None or value == "":
            continue
        
        try:
            # Parse key: subject_timepoint
            parts = key.rsplit("_", 1)
            if len(parts) != 2:
                continue
            
            subject, time_point = parts
            score_value = float(value)
            
            # Validate subject and time_point exist in structure
            if subject not in structure.subject_labels:
                continue
            if time_point not in structure.time_point_labels:
                continue
            
            # Upsert score
            existing = db.query(models.CustomUserScore).filter(
                models.CustomUserScore.user_id == current_user.id,
                models.CustomUserScore.structure_id == structure_id,
                models.CustomUserScore.subject == subject,
                models.CustomUserScore.time_point == time_point
            ).first()
            
            if existing:
                existing.actual_score = score_value
                existing.updated_at = datetime.utcnow()
            else:
                new_score = models.CustomUserScore(
                    user_id=current_user.id,
                    structure_id=structure_id,
                    subject=subject,
                    time_point=time_point,
                    actual_score=score_value
                )
                db.add(new_score)
            
            saved_count += 1
        except (ValueError, TypeError):
            continue
    
    db.commit()
    
    # Trigger prediction for this structure only (if conditions met)
    prediction_result = _trigger_prediction_for_structure(db, current_user.id, structure_id)
    
    response = {
        "message": f"Đã lưu {saved_count} điểm",
        "saved_count": saved_count
    }
    
    if prediction_result["success"]:
        response["message"] += f" và {prediction_result['message']}"
        response["auto_predicted"] = True
        response["predicted_count"] = prediction_result["predicted_count"]
    
    return response


@router.get("/user-scores/{structure_id}")
async def get_user_scores(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get user's scores for a specific structure"""
    # Verify structure ownership
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")
    
    scores = db.query(models.CustomUserScore).filter(
        models.CustomUserScore.user_id == current_user.id,
        models.CustomUserScore.structure_id == structure_id
    ).all()
    
    result = {}
    for score in scores:
        key = f"{score.subject}_{score.time_point}"
        result[key] = {
            "actual_score": score.actual_score,
            "predicted_score": score.predicted_score,
            "predicted_source": score.predicted_source,
            "predicted_status": score.predicted_status
        }
    
    return {"scores": result}


@router.post("/predict/{structure_id}")
async def predict_custom_scores(
    structure_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Run prediction for custom structure using selected ML model and parameters"""
    body = await request.json()
    current_time_point = body.get("current_time_point")
    
    if not current_time_point:
        raise HTTPException(status_code=400, detail="current_time_point is required")
    
    # Verify structure ownership
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id,
        models.CustomTeachingStructure.user_id == current_user.id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")
    
    if current_time_point not in structure.time_point_labels:
        raise HTTPException(status_code=400, detail="Invalid current_time_point")
    
    # Check if reference dataset exists
    reference_count = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).count()
    
    if reference_count == 0:
        raise HTTPException(status_code=400, detail="No reference dataset uploaded")
    
    # Get active ML model and parameters (shared from main system)
    model_config = db.query(models.MLModelConfig).first()
    active_model = model_config.active_model if model_config else "knn"
    
    model_params = db.query(models.ModelParameters).first()
    if not model_params:
        model_params = models.ModelParameters(knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
        db.add(model_params)
        db.commit()
        db.refresh(model_params)
    
    # Run prediction using custom prediction service
    from ml.custom_prediction_service import update_predictions_for_custom_structure
    
    predicted_count = update_predictions_for_custom_structure(
        db=db,
        user_id=current_user.id,
        structure_id=structure_id,
        current_time_point=current_time_point,
        active_model=active_model,
        model_params=model_params
    )
    
    return {
        "message": f"Đã dự đoán {predicted_count} điểm",
        "predicted_count": predicted_count,
        "model_used": active_model
    }

