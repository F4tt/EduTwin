"""
Custom Model API
Allows users to define custom teaching structures and upload custom datasets
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, BackgroundTasks
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
from ml.prediction_cache import invalidate_prediction_cache, invalidate_evaluation_cache

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
    
    # Load model config and parameters from database
    try:
        # Get active model
        config = db.query(models.MLModelConfig).first()
        if not config:
            config = models.MLModelConfig(id=1, active_model="knn")
            db.add(config)
            db.commit()
            db.refresh(config)
        active_model = config.active_model
        
        # Get model parameters
        params = db.query(models.ModelParameters).first()
        if not params:
            params = models.ModelParameters(id=1, knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
            db.add(params)
            db.commit()
            db.refresh(params)
        
        model_params = {
            "knn_n": params.knn_n,
            "kr_bandwidth": params.kr_bandwidth,
            "lwlr_tau": params.lwlr_tau
        }
        
        from ml.prediction_service import update_predictions_for_custom_structure
        
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
    scale_type: str = '0-10'  # '0-10', '0-100', '0-10000', 'A-F', 'GPA'

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
    
    @field_validator('scale_type')
    @classmethod
    def validate_scale_type(cls, v: str) -> str:
        valid_scales = ['0-10', '0-100', '0-10000', 'A-F', 'GPA']
        if v not in valid_scales:
            raise ValueError(f"Thang điểm không hợp lệ. Phải là một trong: {', '.join(valid_scales)}")
        return v


class TogglePipelineRequest(BaseModel):
    enabled: bool


class EvaluateModelsRequest(BaseModel):
    structure_id: int
    input_timepoints: List[str]  # List of timepoint labels
    output_timepoints: List[str]  # List of timepoint labels


@router.get("/get-active-structure")
async def get_active_structure(
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get globally active teaching structure (no auth required for read)"""
    structure = db.query(models.CustomTeachingStructure).filter(
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
        "scale_type": structure.scale_type if hasattr(structure, 'scale_type') else '0-10',
        "created_at": structure.created_at.isoformat() if structure.created_at else None
    }


# update-current-time-point endpoint removed - users manage their own time points via CustomUserScore


@router.get("/teaching-structures")
async def get_all_teaching_structures(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all teaching structures (admin only)"""
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can view structures")
    
    print(f"[DEBUG] Admin {current_user.id} fetching all structures")
    
    structures = db.query(models.CustomTeachingStructure).order_by(
        models.CustomTeachingStructure.created_at.desc()
    ).all()
    
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
                "scale_type": s.scale_type if hasattr(s, 'scale_type') else '0-10',
                # current_time_point removed from structure
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
    """Activate a specific teaching structure (admin only, global)"""
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can activate structures")
    
    # Find the structure (global, no user_id check)
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu trúc")
    
    # Deactivate ALL structures globally (only one can be active)
    db.query(models.CustomTeachingStructure).update({"is_active": False})
    
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
    """Delete a teaching structure (admin only)"""
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can delete structures")
    
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
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
    """Save new teaching structure (admin only, global)"""
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can create structures")
    
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
    
    # Check max limit (10 global structures)
    count = db.query(models.CustomTeachingStructure).count()
    
    if count >= 10:
        raise HTTPException(
            status_code=400,
            detail="Hệ thống đã đạt giới hạn tối đa 10 cấu trúc. Vui lòng xóa một cấu trúc cũ trước."
        )
    
    # Check for duplicate name (globally)
    duplicate = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.structure_name == structure.structure_name
    ).first()
    
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail=f"Cấu trúc với tên '{structure.structure_name}' đã tồn tại"
        )
    
    # Create new structure (inactive by default)
    new_structure = models.CustomTeachingStructure(
        # user_id removed - structure is global
        structure_name=structure.structure_name,
        num_time_points=structure.num_time_points,
        num_subjects=structure.num_subjects,
        time_point_labels=[tp.strip() for tp in structure.time_point_labels],
        subject_labels=[subj.strip() for subj in structure.subject_labels],
        scale_type=structure.scale_type,
        is_active=False
    )
    db.add(new_structure)
    db.commit()
    db.refresh(new_structure)
    
    print(f"[DEBUG] Admin {current_user.id} created global structure: ID={new_structure.id}, Name={new_structure.structure_name}")
    
    return {
        "message": "Cấu trúc giảng dạy đã được lưu thành công",
        "structure_id": new_structure.id
    }


@router.get("/pipeline-status")
async def get_pipeline_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get custom model pipeline status for globally active structure"""
    structure = db.query(models.CustomTeachingStructure).filter(
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
    """Toggle custom model pipeline on/off for globally active structure (admin only)"""
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can toggle pipeline")
    
    structure = db.query(models.CustomTeachingStructure).filter(
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


@router.post("/trigger-pipeline/{structure_id}")
async def trigger_pipeline_for_structure(
    structure_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Manually trigger ML pipeline for a structure"""
    print(f"[trigger-pipeline] User {current_user.id} triggering for structure {structure_id}")
    
    result = _trigger_prediction_for_structure(db, current_user.id, structure_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return {
        "message": result["message"],
        "predicted_count": result.get("predicted_count", 0),
        "model_used": result.get("model_used", "knn")
    }


@router.post("/upload-dataset/{structure_id}")
async def upload_custom_dataset(
    structure_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Upload custom dataset for a specific structure (admin only)"""
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can upload datasets")
    
    # Invalidate cache for this structure since reference data is changing
    invalidate_evaluation_cache(structure_id=structure_id)
    invalidate_prediction_cache(structure_id=structure_id)
    
    # Find the specific structure
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    print(f"[UPLOAD] User {current_user.id} uploading to structure: {structure.id if structure else None}")
    
    if not structure:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy cấu trúc giảng dạy."
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
    
    print(f"[UPLOAD] Expected columns: {expected_score_columns}")
    print(f"[UPLOAD] Found columns: {list(df.columns)}")
    print(f"[UPLOAD] Missing columns: {missing_columns}")
    
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
            # user_id removed - dataset is global
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
    """Get statistics about uploaded custom dataset for globally active structure"""
    structure = db.query(models.CustomTeachingStructure).filter(
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
    # Verify structure exists
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
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
    
    print(f"[SAVE_SCORES] User {current_user.id} saving {len(scores)} scores for structure {structure_id}")
    
    if not structure_id:
        raise HTTPException(status_code=400, detail="structure_id is required")
    
    # Verify structure exists (users can save scores to any structure)
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")
    
    saved_count = 0
    
    for key, value in scores.items():
        if not key:
            continue
        
        try:
            # Parse key: subject_timepoint
            # Need to match against structure's actual subjects and timepoints
            # to handle subjects/timepoints that may contain underscores
            subject = None
            time_point = None
            
            # Try to find matching subject and timepoint
            for s in structure.subject_labels:
                for tp in structure.time_point_labels:
                    expected_key = f"{s}_{tp}"
                    if key == expected_key:
                        subject = s
                        time_point = tp
                        break
                if subject:
                    break
            
            if not subject or not time_point:
                print(f"[SAVE_SCORES] Could not parse key: {key}")
                continue
            
            print(f"[SAVE_SCORES] Parsed key '{key}' -> subject='{subject}', timepoint='{time_point}', value='{value}'")
            
            # Handle deletion (value is None or empty string)
            if value is None or value == "":
                existing = db.query(models.CustomUserScore).filter(
                    models.CustomUserScore.user_id == current_user.id,
                    models.CustomUserScore.structure_id == structure_id,
                    models.CustomUserScore.subject == subject,
                    models.CustomUserScore.time_point == time_point
                ).first()
                
                if existing:
                    existing.actual_score = None
                    existing.updated_at = datetime.utcnow()
                    saved_count += 1
                continue
            
            # Normal save
            score_value = float(value)
            
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
        except (ValueError, TypeError) as e:
            print(f"[SAVE_SCORES] Error processing key '{key}': {e}")
            continue
    
    db.commit()
    
    print(f"[SAVE_SCORES] Successfully saved {saved_count} scores for user {current_user.id}")
    
    # Invalidate cache for this user+structure since scores changed
    if saved_count > 0:
        invalidate_prediction_cache(user_id=current_user.id, structure_id=structure_id)
    
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
    # Verify structure exists
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
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
    
    # Verify structure exists
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
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
    
    # Load model config and parameters from database
    config = db.query(models.MLModelConfig).first()
    if not config:
        config = models.MLModelConfig(id=1, active_model="knn")
        db.add(config)
        db.commit()
        db.refresh(config)
    active_model = config.active_model
    
    # Get model parameters
    params = db.query(models.ModelParameters).first()
    if not params:
        params = models.ModelParameters(id=1, knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
        db.add(params)
        db.commit()
        db.refresh(params)
    
    model_params = {
        "knn_n": params.knn_n,
        "kr_bandwidth": params.kr_bandwidth,
        "lwlr_tau": params.lwlr_tau
    }
    
    # Run prediction using custom prediction service
    from ml.prediction_service import update_predictions_for_custom_structure
    
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



# In-memory storage for evaluation jobs (in production, use Redis or database)
_evaluation_jobs: Dict[str, Dict] = {}

def _run_evaluation_background(
    evaluation_id: str,
    structure_id: int,
    input_timepoints: List[str],
    output_timepoints: List[str],
    model_params: Dict[str, float],
    reference_count: int
):
    """Background task to run model evaluation"""
    from db.database import SessionLocal
    
    db = SessionLocal()
    try:
        _evaluation_jobs[evaluation_id]["status"] = "running"
        _evaluation_jobs[evaluation_id]["message"] = "Đang đánh giá mô hình..."
        
        # Use cluster-based evaluation for large datasets (>= 3000 samples)
        use_clustering = reference_count >= 3000
        
        if use_clustering:
            print(f"[BACKGROUND] Using cluster-based evaluation for {reference_count} samples")
            from ml.cluster_prototype_service import evaluate_cluster_models
            
            results = evaluate_cluster_models(
                db=db,
                structure_id=structure_id,
                input_timepoints=input_timepoints,
                output_timepoints=output_timepoints,
                model_params=model_params,
                n_clusters=None,
                prototypes_per_cluster=None
            )
        else:
            print(f"[BACKGROUND] Using standard evaluation for {reference_count} samples")
            from ml.custom_prediction_service import evaluate_models_for_structure
            
            results = evaluate_models_for_structure(
                db=db,
                structure_id=structure_id,
                input_timepoints=input_timepoints,
                output_timepoints=output_timepoints,
                model_params=model_params
            )
        
        _evaluation_jobs[evaluation_id]["status"] = "completed"
        _evaluation_jobs[evaluation_id]["results"] = results
        _evaluation_jobs[evaluation_id]["message"] = "Đánh giá hoàn tất!"
        print(f"[BACKGROUND] Evaluation {evaluation_id} completed successfully")
        
    except Exception as e:
        print(f"[BACKGROUND] Evaluation {evaluation_id} failed: {e}")
        _evaluation_jobs[evaluation_id]["status"] = "failed"
        _evaluation_jobs[evaluation_id]["error"] = str(e)
        _evaluation_jobs[evaluation_id]["message"] = f"Lỗi: {str(e)}"
    finally:
        db.close()


@router.post("/evaluate-models")
async def evaluate_models(
    request: EvaluateModelsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Start ML model evaluation as a background task (admin/developer only).
    Returns immediately with an evaluation_id for status polling.
    """
    # Require admin/developer role
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins/developers can evaluate models")
    
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == request.structure_id
    ).first()
    
    if not structure:
        raise HTTPException(status_code=404, detail="Structure not found")
    
    # Validate timepoint labels
    for tp in request.input_timepoints + request.output_timepoints:
        if tp not in structure.time_point_labels:
            raise HTTPException(status_code=400, detail=f"Invalid timepoint: {tp}")
    
    # Check if there's enough reference data
    reference_count = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == request.structure_id
    ).count()
    
    if reference_count == 0:
        return {
            "error": "Không có dữ liệu tham chiếu để đánh giá",
            "models": {}
        }
    
    # Get model parameters
    params = db.query(models.ModelParameters).first()
    if not params:
        params = models.ModelParameters(id=1, knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
        db.add(params)
        db.commit()
        db.refresh(params)
    
    model_params = {
        "knn_n": params.knn_n,
        "kr_bandwidth": params.kr_bandwidth,
        "lwlr_tau": params.lwlr_tau
    }
    
    # Generate unique evaluation ID
    import uuid
    evaluation_id = str(uuid.uuid4())[:8]
    
    # Initialize job status
    _evaluation_jobs[evaluation_id] = {
        "status": "pending",
        "message": "Đang khởi tạo...",
        "structure_id": request.structure_id,
        "reference_count": reference_count,
        "created_at": datetime.utcnow().isoformat(),
        "results": None,
        "error": None
    }
    
    # Add background task
    background_tasks.add_task(
        _run_evaluation_background,
        evaluation_id=evaluation_id,
        structure_id=request.structure_id,
        input_timepoints=request.input_timepoints,
        output_timepoints=request.output_timepoints,
        model_params=model_params,
        reference_count=reference_count
    )
    
    print(f"[API] Started background evaluation {evaluation_id} for {reference_count} samples")
    
    return {
        "evaluation_id": evaluation_id,
        "status": "pending",
        "message": f"Đang đánh giá {reference_count} mẫu dữ liệu...",
        "reference_count": reference_count
    }


@router.get("/evaluate-status/{evaluation_id}")
async def get_evaluation_status(
    evaluation_id: str,
    current_user: models.User = Depends(get_current_user)
):
    """
    Get the status of a background evaluation job.
    Poll this endpoint to check if evaluation is complete.
    """
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins/developers can check evaluation status")
    
    if evaluation_id not in _evaluation_jobs:
        raise HTTPException(status_code=404, detail="Evaluation job not found")
    
    job = _evaluation_jobs[evaluation_id]
    
    response = {
        "evaluation_id": evaluation_id,
        "status": job["status"],
        "message": job["message"],
        "reference_count": job.get("reference_count", 0)
    }
    
    if job["status"] == "completed":
        response["results"] = job["results"]
        # Clean up completed job after returning results (keep for 5 minutes)
        # In production, use proper TTL-based cleanup
    elif job["status"] == "failed":
        response["error"] = job.get("error", "Unknown error")
    
    return response


# Cache Management Endpoints

@router.get("/cache/stats")
async def get_cache_stats(
    current_user: models.User = Depends(get_current_user)
):
    """Get cache statistics (admin/developer only)"""
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can view cache stats")
    
    from ml.prediction_cache import get_cache_stats
    return get_cache_stats()


@router.post("/cache/invalidate")
async def invalidate_cache(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Manually invalidate cache (admin/developer only)"""
    if current_user.role not in ['admin', 'developer']:
        raise HTTPException(status_code=403, detail="Only admins can invalidate cache")
    
    body = await request.json()
    cache_type = body.get("cache_type", "all")  # "prediction", "evaluation", or "all"
    structure_id = body.get("structure_id")  # Optional: only invalidate for specific structure
    user_id = body.get("user_id")  # Optional: only invalidate for specific user
    
    deleted_count = 0
    
    if cache_type in ["prediction", "all"]:
        deleted_count += invalidate_prediction_cache(user_id=user_id, structure_id=structure_id)
    
    if cache_type in ["evaluation", "all"]:
        deleted_count += invalidate_evaluation_cache(structure_id=structure_id)
    
    return {
        "message": f"Invalidated {deleted_count} cache keys",
        "deleted_count": deleted_count,
        "cache_type": cache_type,
        "structure_id": structure_id,
        "user_id": user_id
    }
