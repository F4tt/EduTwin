from datetime import datetime
from typing import Dict, List, Optional
import json
import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

logger = logging.getLogger("uvicorn.error")

from db import models, database
from core.study_constants import GRADE_ORDER, SEMESTER_ORDER, SUBJECTS
from ml import prediction_service
from services.chatbot_service import generate_chat_response
from utils.session_utils import require_auth, get_current_user

router = APIRouter(prefix="/learning-goals", tags=["LearningGoals"])


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_next_semester(current_semester: str, current_grade: str) -> tuple[str, str]:
    """Calculate the next semester based on current semester and grade."""
    try:
        grade_idx = GRADE_ORDER.index(current_grade)
        semester_list = SEMESTER_ORDER[current_grade]
        semester_idx = semester_list.index(current_semester)
        
        # If there's a next semester in the same grade
        if semester_idx + 1 < len(semester_list):
            return semester_list[semester_idx + 1], current_grade
        
        # Move to next grade, first semester
        if grade_idx + 1 < len(GRADE_ORDER):
            next_grade = GRADE_ORDER[grade_idx + 1]
            return SEMESTER_ORDER[next_grade][0], next_grade
        
        # If already at last semester, return the same
        return current_semester, current_grade
    except (ValueError, IndexError, KeyError):
        return "2", "12"  # Default fallback


def predict_scores_for_target(
    db: Session,
    user_id: int,
    target_average: float,
    target_semester: str,
    target_grade: str
) -> Dict[str, float]:
    """
    Predict individual subject scores that would achieve the target average.
    Uses the ML pipeline with goal-based optimization.
    """
    from ml.knn_common import build_feature_key
    
    # Get current scores for the user
    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    
    # Build actual_map from current scores
    actual_map: Dict[str, float] = {}
    for score in scores:
        if score.actual_score is not None:
            key = build_feature_key(score.subject, score.semester, score.grade_level)
            actual_map[key] = float(score.actual_score)
    
    # Load reference dataset
    dataset = prediction_service._load_reference_dataset(db)
    if not dataset:
        return {}
    
    # Get model parameters
    model_params = db.query(models.ModelParameters).first()
    if not model_params:
        model_params = models.ModelParameters(knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
    
    # Find samples in reference dataset that match the target average for target semester
    matching_samples = []
    for sample in dataset:
        # Calculate average for target semester from this sample
        target_keys = [
            build_feature_key(subj, target_semester, target_grade)
            for subj in SUBJECTS
        ]
        values = [sample.get(key) for key in target_keys if sample.get(key) is not None]
        if values:
            sample_avg = sum(values) / len(values)
            # Accept samples within ±0.5 of target
            if abs(sample_avg - target_average) <= 0.5:
                matching_samples.append((abs(sample_avg - target_average), sample))
    
    if not matching_samples:
        # Fallback: use uniform distribution
        return {subj: target_average for subj in SUBJECTS}
    
    # Sort by closest match and take top k
    matching_samples.sort(key=lambda x: x[0])
    k = min(model_params.knn_n, len(matching_samples))
    top_matches = matching_samples[:k]
    
    # Average the subject scores from top matching samples
    predicted_scores: Dict[str, float] = {}
    for subject in SUBJECTS:
        key = build_feature_key(subject, target_semester, target_grade)
        values = [sample.get(key) for _, sample in top_matches if sample.get(key) is not None]
        if values:
            predicted_scores[subject] = round(sum(values) / len(values), 2)
        else:
            predicted_scores[subject] = target_average
    
    return predicted_scores


def build_trajectory_data(
    db: Session,
    user_id: int,
    target_semester: str,
    target_grade: str,
    predicted_scores: Dict[str, float]
) -> List[Dict]:
    """
    Build trajectory data for line chart showing current path and goal path.
    Goal path includes all terms from start to target (with past = current, future = predicted).
    Returns data for all semesters up to and including target.
    """
    from ml.knn_common import build_feature_key
    
    # Get current grade to determine split point
    user = db.query(models.User).filter(models.User.id == user_id).first()
    current_grade_token = getattr(user, "current_grade", None) if user else None
    
    # Get all scores for the user
    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    
    # Build term order up to target
    term_order = []
    for grade in GRADE_ORDER:
        for semester in SEMESTER_ORDER[grade]:
            term_order.append(f"{semester}_{grade}")
            if semester == target_semester and grade == target_grade:
                break
        if term_order and term_order[-1] == f"{target_semester}_{target_grade}":
            break
    
    # Find current grade index
    current_idx = None
    if current_grade_token:
        try:
            current_idx = term_order.index(current_grade_token)
        except ValueError:
            pass
    
    # Calculate averages for each term
    trajectory = []
    for idx, term in enumerate(term_order):
        semester, grade = term.split("_")
        
        # Get actual/predicted scores for this term
        term_scores = [
            s for s in scores
            if s.semester == semester and s.grade_level == grade
        ]
        
        values = []
        for score in term_scores:
            val = score.actual_score if score.actual_score is not None else score.predicted_score
            if val is not None:
                values.append(float(val))
        
        current_avg = round(sum(values) / len(values), 2) if values else None
        
        # For goal path: use current values before/at current_idx, predicted at target
        if current_idx is not None and idx <= current_idx:
            # Past/current: goal = current (will be covered by solid line)
            goal_avg = current_avg
        elif term == f"{target_semester}_{target_grade}":
            # Target term: use predicted goal average
            goal_avg = round(sum(predicted_scores.values()) / len(predicted_scores), 2) if predicted_scores else None
        else:
            # Between current and target: no data (will be interpolated by chart)
            goal_avg = None
        
        trajectory.append({
            "term": term,
            "current": current_avg,
            "goal": goal_avg
        })
    
    return trajectory


class LearningGoalRequest(BaseModel):
    target_average: float
    
    @field_validator("target_average")
    @classmethod
    def validate_average(cls, v: float) -> float:
        if v < 0 or v > 10:
            raise ValueError("Điểm trung bình phải nằm trong khoảng 0-10")
        return v


def generate_ai_analysis_background(
    user_id: int,
    goal_id: int,
    target_average: float,
    target_semester: str,
    target_grade: str,
    predicted_scores: Dict[str, float],
    trajectory_data: List[Dict]
):
    """Background task to generate AI analysis and update the goal."""
    try:
        from db.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Get user data
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found for AI analysis")
                return
            
            # Build user dict for generate_goal_analysis
            user_dict = {"user_id": user_id, "username": user.username}
            
            # Generate AI analysis (this is async, so we need to run it properly)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ai_analysis = loop.run_until_complete(
                generate_goal_analysis(
                    db, user_dict, target_average,
                    target_semester, target_grade,
                    predicted_scores, trajectory_data
                )
            )
            loop.close()
            
            # Update the goal with AI analysis
            goal = db.query(models.LearningGoal).filter(models.LearningGoal.id == goal_id).first()
            if goal:
                goal.ai_analysis = ai_analysis
                goal.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"[LEARNING_GOAL] AI analysis generated for goal {goal_id}")
            else:
                logger.error(f"Goal {goal_id} not found for AI analysis update")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[LEARNING_GOAL] Error in background AI analysis: {e}")


@router.post("/set-goal")
@require_auth
async def set_learning_goal(
    request: Request,
    payload: LearningGoalRequest,
    db: Session = Depends(get_db)
):
    """Set a new learning goal for the user WITHOUT generating AI strategy."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    user_id = current_user.get("user_id")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    # Get current grade
    current_grade_token = getattr(user, "current_grade", None)
    if not current_grade_token:
        raise HTTPException(status_code=400, detail="Vui lòng thiết lập học kỳ hiện tại trước")
    
    try:
        current_semester, current_grade = current_grade_token.split("_")
    except ValueError:
        raise HTTPException(status_code=400, detail="Học kỳ hiện tại không hợp lệ")
    
    # Calculate target semester (next semester)
    target_semester, target_grade = get_next_semester(current_semester, current_grade)
    
    # Predict scores for target
    predicted_scores = predict_scores_for_target(
        db, user_id, payload.target_average, target_semester, target_grade
    )
    
    # Build trajectory data
    trajectory_data = build_trajectory_data(
        db, user_id, target_semester, target_grade, predicted_scores
    )
    
    # Save or update learning goal WITHOUT AI analysis
    existing_goal = (
        db.query(models.LearningGoal)
        .filter(models.LearningGoal.user_id == user_id)
        .order_by(models.LearningGoal.created_at.desc())
        .first()
    )
    
    if existing_goal:
        existing_goal.target_average = payload.target_average
        existing_goal.target_semester = target_semester
        existing_goal.target_grade_level = target_grade
        existing_goal.predicted_scores = predicted_scores
        existing_goal.trajectory_data = trajectory_data
        existing_goal.ai_analysis = None  # Clear old AI analysis
        existing_goal.updated_at = datetime.utcnow()
        goal = existing_goal
    else:
        goal = models.LearningGoal(
            user_id=user_id,
            target_average=payload.target_average,
            target_semester=target_semester,
            target_grade_level=target_grade,
            predicted_scores=predicted_scores,
            trajectory_data=trajectory_data,
            ai_analysis=None  # No AI analysis on goal creation
        )
        db.add(goal)
    
    db.commit()
    db.refresh(goal)
    
    logger.info(f"[LEARNING_GOAL] Goal {goal.id} created/updated without AI strategy")
    
    return JSONResponse(content={
        "id": goal.id,
        "target_average": goal.target_average,
        "target_semester": goal.target_semester,
        "target_grade_level": goal.target_grade_level,
        "predicted_scores": goal.predicted_scores,
        "trajectory_data": goal.trajectory_data,
        "ai_analysis": goal.ai_analysis,
        "created_at": goal.created_at.isoformat(),
        "updated_at": goal.updated_at.isoformat()
    })


class GenerateStrategyRequest(BaseModel):
    goal_id: int


@router.post("/generate-strategy")
@require_auth
async def generate_learning_strategy(
    request: Request,
    payload: GenerateStrategyRequest,
    db: Session = Depends(get_db)
):
    """Generate AI strategy for an existing learning goal."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    user_id = current_user.get("user_id")
    
    # Get the goal
    goal = db.query(models.LearningGoal).filter(
        models.LearningGoal.id == payload.goal_id,
        models.LearningGoal.user_id == user_id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Không tìm thấy mục tiêu học tập")
    
    # Generate AI analysis
    ai_analysis = await generate_goal_analysis(
        db, current_user, goal.target_average,
        goal.target_semester, goal.target_grade_level,
        goal.predicted_scores, goal.trajectory_data
    )
    
    # Update the goal with AI analysis
    goal.ai_analysis = ai_analysis
    goal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(goal)
    
    logger.info(f"[LEARNING_GOAL] AI strategy generated for goal {goal.id}")
    
    return JSONResponse(content={
        "id": goal.id,
        "ai_analysis": goal.ai_analysis,
        "updated_at": goal.updated_at.isoformat()
    })


@router.get("/current-goal")
@require_auth
def get_current_goal(request: Request, db: Session = Depends(get_db)):
    """Get the current learning goal for the user."""
    current_user = get_current_user(request)
    if not current_user:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    
    user_id = current_user.get("user_id")
    goal = (
        db.query(models.LearningGoal)
        .filter(models.LearningGoal.user_id == user_id)
        .order_by(models.LearningGoal.created_at.desc())
        .first()
    )
    
    if not goal:
        return {"has_goal": False}
    
    return {
        "has_goal": True,
        "id": goal.id,
        "target_average": goal.target_average,
        "target_semester": goal.target_semester,
        "target_grade_level": goal.target_grade_level,
        "predicted_scores": goal.predicted_scores,
        "trajectory_data": goal.trajectory_data,
        "ai_analysis": goal.ai_analysis,
        "created_at": goal.created_at.isoformat(),
        "updated_at": goal.updated_at.isoformat()
    }


async def generate_goal_analysis(
    db: Session,
    user: Dict,
    target_average: float,
    target_semester: str,
    target_grade: str,
    predicted_scores: Dict[str, float],
    trajectory_data: List[Dict]
) -> str:
    """Generate AI analysis comparing current performance with goal."""
    from core.study_constants import SUBJECT_DISPLAY
    from services.educational_knowledge import get_educational_context, get_gpa_classification
    from services.dataset_analyzer import get_dataset_insights_for_llm, find_similar_achievers
    
    # Get current scores
    user_id = user.get("user_id")
    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    
    # Calculate current average
    current_values = []
    for score in scores:
        val = score.actual_score if score.actual_score is not None else score.predicted_score
        if val is not None:
            current_values.append(float(val))
    
    current_avg = round(sum(current_values) / len(current_values), 2) if current_values else None
    
    # Get educational context and benchmarks
    edu_context = get_educational_context()
    dataset_insights = get_dataset_insights_for_llm(db, user_id)
    
    # Find similar achievers
    similar_students = find_similar_achievers(db, user_id, target_average, top_k=5)
    similar_info = ""
    if similar_students.get("status") == "success":
        similar_info = f"\n\n# HỌC SINH TƯƠNG TỰ:\n{similar_students.get('summary', '')}"
    
    # Get GPA classification
    current_classification = get_gpa_classification(current_avg) if current_avg else {}
    target_classification = get_gpa_classification(target_average)
    
    # Build prompt for AI
    prompt = f"""Bạn là cố vấn học tập chuyên nghiệp của EduTwin.

# KIẾN THỨC:
{edu_context[:1500]}

{dataset_insights[:500] if dataset_insights else ''}

THÔNG TIN HIỆN TẠI:
- Điểm TB: {current_avg if current_avg else 'Chưa có'}
- Xếp loại: {current_classification.get('level', 'N/A')}
- Số môn: {len(current_values)}

MỤC TIÊU:
- HK {target_semester} lớp {target_grade}
- Điểm TB mục tiêu: {target_average}
- Xếp loại: {target_classification.get('level')}
- Cần tăng: {round(target_average - (current_avg or 0), 2) if current_avg else target_average} điểm

ĐIỂM DỰ ĐOÁN:
{json.dumps({SUBJECT_DISPLAY.get(k, k): v for k, v in predicted_scores.items()}, ensure_ascii=False, indent=2)}
{similar_info}

VIẾT 6 ĐOẠN (mỗi đoạn 4-6 câu, văn bản thuần, KHÔNG markdown):

1. So sánh hiện tại-mục tiêu: Khoảng cách, mức độ khả thi, số điểm cần tăng
2. Môn cần cải thiện: TOP 3 môn, số điểm cần tăng, môn đã đạt
3. Điểm mạnh: 2-3 môn thế mạnh, vị trí so benchmark, cách duy trì
4. Điểm yếu: 2-3 môn yếu, roadmap cụ thể, phương pháp
5. Chiến lược: Phân bổ thời gian, phương pháp, lộ trình, milestone
6. Động viên: Đánh giá khả năng, khích lệ, lời khuyên

Dùng SỐ LIỆU thực tế, ngôn ngữ thân thiện."""
    
    try:
        result = await generate_chat_response(
            db=db,
            user=user,
            message=prompt,
            session_id="__silent__"
        )
        analysis = result.get("answer", "").strip()
    except Exception as e:
        logger.error(f"Failed to generate goal analysis: {e}")
        analysis = f"Để đạt mục tiêu {target_average} điểm ở học kỳ {target_semester} lớp {target_grade}, bạn cần nỗ lực cải thiện ở các môn học theo dự đoán trên."
    
    return analysis
