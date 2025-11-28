"""
Dataset Analyzer Service
Converts Excel data into insights and benchmarks for LLM context.
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from db import models
from ml.knn_common import build_feature_key
from core.study_constants import SUBJECTS
import json


def analyze_reference_dataset(db: Session, user_id: Optional[int] = None) -> Dict:
    """
    Analyze the reference dataset to extract statistical insights.
    Returns comprehensive statistics about score distribution.
    Dataset is shared across all users (managed by admin/developer).
    user_id parameter kept for API compatibility but not used.
    """
    from ml import prediction_service
    
    dataset = prediction_service._load_reference_dataset(db)
    if not dataset:
        return {"status": "no_data"}
    
    # Calculate overall statistics
    all_scores = []
    subject_stats = {subj: [] for subj in SUBJECTS}
    
    for record in dataset:
        record_scores = []
        for subj in SUBJECTS:
            # Try to find scores for this subject across all semesters/grades
            for key, value in record.items():
                if subj.lower() in key.lower() and isinstance(value, (int, float)) and 0 <= value <= 10:
                    record_scores.append(value)
                    subject_stats[subj].append(value)
        
        if record_scores:
            all_scores.extend(record_scores)
    
    if not all_scores:
        return {"status": "no_valid_scores"}
    
    all_scores.sort()
    
    # Calculate percentiles
    def percentile(data, p):
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        return data[f] + (k - f) * (data[c] - data[f])
    
    stats = {
        "total_records": len(dataset),
        "total_scores": len(all_scores),
        "mean": round(sum(all_scores) / len(all_scores), 2),
        "median": round(percentile(all_scores, 50), 2),
        "p10": round(percentile(all_scores, 10), 2),
        "p25": round(percentile(all_scores, 25), 2),
        "p75": round(percentile(all_scores, 75), 2),
        "p90": round(percentile(all_scores, 90), 2),
        "min": round(min(all_scores), 2),
        "max": round(max(all_scores), 2),
        "subjects": {}
    }
    
    # Calculate per-subject statistics
    for subj, scores in subject_stats.items():
        if scores:
            scores.sort()
            stats["subjects"][subj] = {
                "mean": round(sum(scores) / len(scores), 2),
                "median": round(percentile(scores, 50), 2),
                "p75": round(percentile(scores, 75), 2),
                "p90": round(percentile(scores, 90), 2),
                "count": len(scores)
            }
    
    return stats


def get_user_benchmark_summary(db: Session, user_id: int) -> Dict:
    """
    Generate a summary comparing user's performance with the dataset benchmark.
    Returns a text summary suitable for LLM context.
    """
    # Get user's scores
    user_scores = db.query(models.StudyScore).filter(
        models.StudyScore.user_id == user_id
    ).all()
    
    if not user_scores:
        return {"has_data": False}
    
    # Calculate user's average (exclude TN graduation exam)
    user_values = []
    subject_scores = {}
    
    for score in user_scores:
        # Skip graduation exam entries
        if score.semester == 'TN' or score.grade_level == 'TN':
            continue
            
        val = score.actual_score if score.actual_score is not None else score.predicted_score
        if val is not None and 0 <= val <= 10:
            user_values.append(float(val))
            if score.subject not in subject_scores:
                subject_scores[score.subject] = []
            subject_scores[score.subject].append(float(val))
    
    if not user_values:
        return {"has_data": False}
    
    user_avg = sum(user_values) / len(user_values)
    
    # Get dataset statistics (shared dataset)
    dataset_stats = analyze_reference_dataset(db)
    if dataset_stats.get("status") in ["no_data", "no_valid_scores"]:
        return {"has_data": False}
    
    # Calculate percentile
    median = dataset_stats.get("median", 6.5)
    p75 = dataset_stats.get("p75", 7.5)
    p90 = dataset_stats.get("p90", 8.5)
    
    if user_avg >= p90:
        position = f"Top 10% (Xuất sắc - điểm trung bình {user_avg:.1f} >= {p90})"
    elif user_avg >= p75:
        position = f"Top 25% (Giỏi - điểm trung bình {user_avg:.1f} >= {p75})"
    elif user_avg >= median:
        position = f"Trên trung bình (Khá - điểm trung bình {user_avg:.1f} >= {median})"
    else:
        position = f"Cần cải thiện (điểm trung bình {user_avg:.1f} < {median})"
    
    # Subject-specific comparison
    subject_comparison = []
    for subj, scores in subject_scores.items():
        subj_avg = sum(scores) / len(scores)
        subj_stats = dataset_stats.get("subjects", {}).get(subj)
        if subj_stats:
            subj_median = subj_stats.get("median", 0)
            if subj_avg >= subj_stats.get("p90", 9):
                subject_comparison.append(f"  - {subj}: {subj_avg:.1f} (Top 10%)")
            elif subj_avg >= subj_stats.get("p75", 7.5):
                subject_comparison.append(f"  - {subj}: {subj_avg:.1f} (Khá/Giỏi)")
            elif subj_avg >= subj_median:
                subject_comparison.append(f"  - {subj}: {subj_avg:.1f} (Trên TB)")
            else:
                subject_comparison.append(f"  - {subj}: {subj_avg:.1f} (Cần cải thiện)")
    
    summary = (
        f"Vị trí so với {dataset_stats['total_records']} học sinh: {position}\n"
        f"Điểm trung bình mặt bằng chung: {median}\n"
    )
    
    if subject_comparison:
        summary += "So sánh theo môn:\n" + "\n".join(subject_comparison)
    
    return {
        "has_data": True,
        "user_average": round(user_avg, 2),
        "position": position,
        "dataset_median": median,
        "dataset_p75": p75,
        "dataset_p90": p90,
        "summary": summary
    }


def find_similar_achievers(db: Session, user_id: int, target_average: float, top_k: int = 5) -> Dict:
    """
    Find students from reference dataset who achieved similar target average.
    Returns their characteristics and patterns.
    """
    from ml import prediction_service
    from ml.knn_common import build_feature_key
    
    dataset = prediction_service._load_reference_dataset(db)
    if not dataset:
        return {"status": "no_data"}
    
    # Get user's current scores
    user_scores = db.query(models.StudyScore).filter(
        models.StudyScore.user_id == user_id
    ).all()
    
    user_score_map = {}
    for score in user_scores:
        val = score.actual_score if score.actual_score is not None else score.predicted_score
        if val is not None:
            key = build_feature_key(score.subject, score.semester, score.grade_level)
            user_score_map[key] = float(val)
    
    # Find records with similar target average
    similar_records = []
    
    for record in dataset:
        record_scores = [v for v in record.values() if isinstance(v, (int, float)) and 0 <= v <= 10]
        if not record_scores:
            continue
        
        record_avg = sum(record_scores) / len(record_scores)
        
        # Accept records within ±0.5 of target
        if abs(record_avg - target_average) <= 0.5:
            # Calculate difference from user's current state
            common_subjects = set(user_score_map.keys()) & set(record.keys())
            if common_subjects:
                diff = sum(abs(record.get(k, 0) - user_score_map.get(k, 0)) for k in common_subjects) / len(common_subjects)
            else:
                diff = abs(record_avg - (sum(user_score_map.values()) / len(user_score_map) if user_score_map else target_average))
            
            similar_records.append({
                "average": round(record_avg, 2),
                "difference": round(diff, 2),
                "record": record
            })
    
    if not similar_records:
        return {"status": "no_similar_students"}
    
    # Sort by similarity (smallest difference first)
    similar_records.sort(key=lambda x: x["difference"])
    top_similar = similar_records[:top_k]
    
    # Analyze patterns
    subject_patterns = {}
    for subj in SUBJECTS:
        values = []
        for rec in top_similar:
            for key, val in rec["record"].items():
                if subj.lower() in key.lower() and isinstance(val, (int, float)) and 0 <= val <= 10:
                    values.append(val)
        
        if values:
            subject_patterns[subj] = {
                "average": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2)
            }
    
    return {
        "status": "success",
        "found_count": len(similar_records),
        "target_average": target_average,
        "top_similar": [{
            "average": rec["average"],
            "difference_from_user": rec["difference"]
        } for rec in top_similar],
        "subject_patterns": subject_patterns,
        "summary": _generate_similarity_summary(target_average, len(similar_records), subject_patterns)
    }


def _generate_similarity_summary(target: float, count: int, patterns: Dict) -> str:
    """Generate human-readable summary of similar achievers."""
    summary = f"Có {count} học sinh trong dữ liệu tham khảo đạt mục tiêu ~{target} điểm.\n"
    summary += "Đặc điểm chung của họ:\n"
    
    for subj, stats in patterns.items():
        summary += f"  - {subj}: trung bình {stats['average']}, dao động {stats['min']}-{stats['max']}\n"
    
    return summary


def get_dataset_insights_for_llm(db: Session, user_id: Optional[int] = None) -> str:
    """
    Generate comprehensive dataset insights formatted for LLM context.
    
    Args:
        db: Database session
        user_id: Optional user ID for personalized comparison
    
    Returns:
        Formatted string with dataset insights
    """
    stats = analyze_reference_dataset(db)
    
    if stats.get("status") in ["no_data", "no_valid_scores"]:
        return ""
    
    insights = f"""
# DỮ LIỆU THAM KHẢO VÀ MẶT BẰNG CHUNG

Dựa trên {stats['total_records']} hồ sơ học sinh với {stats['total_scores']} điểm số:

## Thống kê tổng quát:
- Điểm trung bình: {stats['mean']}
- Điểm trung vị: {stats['median']}
- Top 10% (P90): từ {stats['p90']} trở lên
- Top 25% (P75): từ {stats['p75']} trở lên
- Điểm thấp nhất: {stats['min']}, cao nhất: {stats['max']}

## Thống kê theo môn:
"""
    
    for subj, subj_stats in stats.get("subjects", {}).items():
        insights += f"- {subj}: TB={subj_stats['mean']}, Top 25%>={subj_stats['p75']}, Top 10%>={subj_stats['p90']}\n"
    
    if user_id:
        user_benchmark = get_user_benchmark_summary(db, user_id)
        if user_benchmark.get("has_data"):
            insights += f"\n## Vị trí của học sinh này:\n{user_benchmark['summary']}\n"
    
    return insights
