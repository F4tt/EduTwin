"""
ML Version Manager - Efficient prediction updates using lazy evaluation
"""
from sqlalchemy.orm import Session
from db import models
from ml import prediction_service
from services import learning_documents
from services.vector_store_provider import get_vector_store
import logging

logger = logging.getLogger("uvicorn.error")


def get_current_ml_version(db: Session) -> int:
    """Get the current ML configuration version (max of model and params versions)"""
    model_config = db.query(models.MLModelConfig).first()
    model_params = db.query(models.ModelParameters).first()
    
    model_ver = getattr(model_config, 'version', 1) if model_config else 1
    param_ver = getattr(model_params, 'version', 1) if model_params else 1
    
    return max(model_ver, param_ver)


def increment_ml_version(db: Session, config_type: str = 'both'):
    """
    Increment ML version when config changes.
    
    Args:
        config_type: 'model', 'params', or 'both'
    """
    if config_type in ['model', 'both']:
        model_config = db.query(models.MLModelConfig).first()
        if model_config:
            current_version = getattr(model_config, 'version', 1)
            model_config.version = current_version + 1
            logger.info(f"[ML_VERSION] Incremented model version to {model_config.version}")
    
    if config_type in ['params', 'both']:
        model_params = db.query(models.ModelParameters).first()
        if model_params:
            current_version = getattr(model_params, 'version', 1)
            model_params.version = current_version + 1
            logger.info(f"[ML_VERSION] Incremented params version to {model_params.version}")
    
    db.commit()


def user_needs_update(db: Session, user_id: int) -> bool:
    """Check if user's predictions need to be updated"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    
    user_version = getattr(user, 'ml_config_version', 0) or 0
    current_version = get_current_ml_version(db)
    
    needs_update = user_version < current_version
    if needs_update:
        logger.info(f"[ML_VERSION] User {user_id} needs update: v{user_version} -> v{current_version}")
    
    return needs_update


def update_user_predictions(db: Session, user_id: int, force: bool = False):
    """
    Update predictions for a single user if needed.
    
    Args:
        user_id: User ID to update
        force: Force update even if version matches
    """
    if not force and not user_needs_update(db, user_id):
        logger.info(f"[ML_VERSION] User {user_id} predictions are up-to-date, skipping")
        return {"status": "skipped", "reason": "up_to_date"}
    
    try:
        logger.info(f"[ML_VERSION] Updating predictions for user {user_id}...")
        
        # Update predictions
        updates = prediction_service.update_predictions_for_user(db, user_id)
        
        # REMOVED: Vector store sync (not needed for score analytics)
        # if updates:
        #     vector_store = get_vector_store()
        #     learning_documents.sync_score_embeddings(db, vector_store, updates)
        
        # Update user's version
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.ml_config_version = get_current_ml_version(db)
        
        db.commit()
        
        logger.info(f"[ML_VERSION] Updated {len(updates)} predictions for user {user_id}")
        return {
            "status": "success",
            "user_id": user_id,
            "updates_count": len(updates),
            "new_version": user.ml_config_version
        }
        
    except Exception as e:
        logger.error(f"[ML_VERSION] Error updating user {user_id}: {e}")
        db.rollback()
        return {"status": "error", "user_id": user_id, "error": str(e)}


def ensure_user_predictions_updated(db: Session, user_id: int):
    """
    Ensure user has latest predictions. Called on login or when accessing scores.
    This is the main entry point for lazy evaluation.
    """
    if user_needs_update(db, user_id):
        logger.info(f"[ML_VERSION] Auto-updating predictions for user {user_id}")
        return update_user_predictions(db, user_id)
    return {"status": "current", "user_id": user_id}


def mark_all_users_for_update(db: Session):
    """
    Mark all users as needing update (set their version to 0).
    Called after dataset import.
    """
    db.query(models.User).update({"ml_config_version": 0})
    db.commit()
    logger.info("[ML_VERSION] Marked all users for prediction update")
