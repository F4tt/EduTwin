from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import sqrt
from statistics import mean
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from db import models
from ml.knn_common import build_feature_key


def _load_reference_dataset(db: Session) -> List[Dict[str, float]]:
    samples = db.query(models.KNNReferenceSample).all()
    dataset: List[Dict[str, float]] = []
    for sample in samples:
        feature_map = sample.feature_data or {}
        if feature_map:
            dataset.append({k: float(v) for k, v in feature_map.items() if isinstance(v, (int, float))})
    return dataset


def _predict_with_knn(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    k: int = 5,
) -> Dict[str, float]:
    if not dataset or not actual_map or not target_keys:
        return {}

    neighbors: List[Tuple[float, Dict[str, float]]] = []
    actual_keys = set(actual_map.keys())

    for sample in dataset:
        overlap = actual_keys & sample.keys()
        if not overlap:
            continue
        distance_sq = 0.0
        for key in overlap:
            diff = sample[key] - actual_map[key]
            distance_sq += diff * diff
        neighbors.append((sqrt(distance_sq), sample))

    if not neighbors:
        return {}

    neighbors.sort(key=lambda item: item[0])
    top_neighbors = neighbors[: k if k > 0 else len(neighbors)]

    predictions: Dict[str, float] = {}
    for key in target_keys:
        numerator = 0.0
        denominator = 0.0
        for distance, sample in top_neighbors:
            value = sample.get(key)
            if value is None:
                continue
            weight = 1.0 if distance == 0 else 1.0 / (distance + 1e-6)
            numerator += weight * value
            denominator += weight
        if denominator > 0:
            predictions[key] = round(numerator / denominator, 2)
    return predictions


def _predict_with_knn_per_subject(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    k: int = 5,
) -> Dict[str, float]:
    """
    Predict each target key (subject_semester_grade) independently using KNN.
    This prevents duplicate predictions across different subjects.
    """
    from ml.knn_common import split_feature_key

    if not dataset or not actual_map or not target_keys:
        return {}

    predictions: Dict[str, float] = {}

    for target_key in target_keys:
        try:
            target_subject, target_semester, target_grade = split_feature_key(target_key)
        except ValueError:
            continue

        # For this target, find k nearest neighbors based on actual_map overlap
        neighbors: List[Tuple[float, Dict[str, float]]] = []
        actual_keys = set(actual_map.keys())

        for sample in dataset:
            overlap = actual_keys & sample.keys()
            if not overlap:
                continue
            distance_sq = 0.0
            for key in overlap:
                diff = sample[key] - actual_map[key]
                distance_sq += diff * diff
            neighbors.append((sqrt(distance_sq), sample))

        if not neighbors:
            continue

        neighbors.sort(key=lambda item: item[0])
        top_neighbors = neighbors[: k if k > 0 else len(neighbors)]

        # Predict only this target subject value from its neighbors
        numerator = 0.0
        denominator = 0.0
        for distance, sample in top_neighbors:
            value = sample.get(target_key)
            if value is None:
                continue
            weight = 1.0 if distance == 0 else 1.0 / (distance + 1e-6)
            numerator += weight * value
            denominator += weight

        if denominator > 0:
            predictions[target_key] = round(numerator / denominator, 2)

    return predictions



def _baseline_predictions(
    scores: List[models.StudyScore],
    target_keys: Optional[Set[str]] = None,
) -> Dict[str, float]:
    actual_by_grade: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    overall_actuals: List[float] = []

    for score in scores:
        if score.actual_score is not None:
            overall_actuals.append(score.actual_score)
            actual_by_grade[(score.grade_level, score.semester)].append(score.actual_score)

    if not overall_actuals:
        return {}

    overall_avg = mean(overall_actuals)
    grade_avgs = {key: mean(values) for key, values in actual_by_grade.items()}

    predictions: Dict[str, float] = {}
    for score in scores:
        if score.actual_score is not None:
            continue
        key = build_feature_key(score.subject, score.semester, score.grade_level)
        if target_keys and key not in target_keys:
            continue
        candidate = grade_avgs.get((score.grade_level, score.semester), overall_avg)
        predictions[key] = round(float(candidate), 2)
    return predictions


def update_predictions_for_user(db: Session, user_id: int) -> List[models.StudyScore]:
    from sklearn.impute import KNNImputer
    import numpy as np

    results: List[models.StudyScore] = []
    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    if not scores:
        return results

    # Build chronological feature key ordering
    from core.study_constants import GRADE_ORDER, SEMESTER_ORDER, SUBJECTS

    ordered_slots = []
    for grade in GRADE_ORDER:
        for semester in SEMESTER_ORDER[grade]:
            ordered_slots.append((grade, semester))

    feature_keys = []
    for grade, semester in ordered_slots:
        for subject in SUBJECTS:
            feature_keys.append(build_feature_key(subject, semester, grade))

    # Map existing scores
    row_by_key: Dict[str, models.StudyScore] = {}
    for score in scores:
        key = build_feature_key(score.subject, score.semester, score.grade_level)
        row_by_key[key] = score

    # Count actual scores to determine if KNN should be activated
    actual_count = sum(1 for score in scores if score.actual_score is not None)

    # Determine the user's current grade milestone
    user = db.query(models.User).filter(models.User.id == user_id).first()
    current_grade_token = getattr(user, "current_grade", None)

    # Helper: compare slot order with current_grade_token (format like '1_11' or 'TN_12')
    def slot_index_for_token(token: str) -> int | None:
        if not token:
            return None
        try:
            parts = str(token).split("_")
            if len(parts) != 2:
                return None
            sem, gr = parts[0].upper(), parts[1]
            for idx, (g, s) in enumerate(ordered_slots):
                if g == gr and s == sem:
                    return idx
        except Exception:
            return None
        return None

    current_idx = slot_index_for_token(current_grade_token)

    # Threshold check: if actual_count < 5, skip KNN entirely
    if actual_count < 5:
        # No KNN prediction; only return existing scores without predictions
        return results

    # Build dataset matrix from reference samples
    dataset = _load_reference_dataset(db)
    # columns = feature_keys
    import pandas as pd

    if dataset:
        df_ref = pd.DataFrame(dataset)
        # ensure all feature keys present
        df_ref = df_ref.reindex(columns=feature_keys)
    else:
        df_ref = pd.DataFrame(columns=feature_keys)

    # Build user's vector: use actual_score for keys that are provided
    user_row = [np.nan] * len(feature_keys)
    for idx, key in enumerate(feature_keys):
        row = row_by_key.get(key)
        if row and row.actual_score is not None:
            user_row[idx] = float(row.actual_score)
        else:
            user_row[idx] = np.nan

    # Prepare prediction inputs: we will use KNNImputer only to fill missing input values
    # for keys up to and including the user's current grade. For outputs (keys after
    # current grade) we'll use the custom _predict_with_knn_per_subject function to produce predictions.
    timestamp = datetime.utcnow()

    import pandas as pd

    # Precompute baseline predictions to use as fallback when KNN predictions are missing
    baseline_preds = _baseline_predictions(scores, target_keys=set(feature_keys))

    # Determine input and target key sets based on current_idx
    if current_idx is not None:
        input_keys = feature_keys[: current_idx + 1]
        target_keys = set(feature_keys[current_idx + 1 :])
    else:
        # If no current grade, treat existing actuals as inputs and the rest as targets
        input_keys = [k for k in feature_keys if row_by_key.get(k) and row_by_key[k].actual_score is not None]
        target_keys = set(k for k in feature_keys if k not in input_keys)

    # Build actual_map by imputing missing values among input_keys using KNNImputer
    actual_map: Dict[str, float] = {}
    if input_keys and (not df_ref.empty):
        df_ref_inputs = df_ref.reindex(columns=input_keys)
        try:
            ref_matrix = df_ref_inputs.to_numpy(dtype=float)
            user_inputs = np.array([user_row[feature_keys.index(k)] for k in input_keys], dtype=float)
            if ref_matrix.size == 0:
                n_samples = 0
            else:
                n_samples = ref_matrix.shape[0]
            n_neighbors = min(10, max(1, n_samples))
            imputer = KNNImputer(n_neighbors=n_neighbors)
            stacked = np.vstack([ref_matrix, user_inputs]) if n_samples > 0 else np.vstack([np.array([user_inputs]), user_inputs])
            try:
                imputed = imputer.fit_transform(stacked)
                user_imputed_inputs = imputed[-1]
            except Exception:
                user_imputed_inputs = user_inputs
        except Exception:
            user_imputed_inputs = np.array([user_row[feature_keys.index(k)] for k in input_keys], dtype=float)

        for i, key in enumerate(input_keys):
            val = user_imputed_inputs[i]
            if not pd.isna(val):
                actual_map[key] = float(val)
    else:
        # No imputation possible; fall back to using existing actuals only
        for key in input_keys:
            row = row_by_key.get(key)
            if row and row.actual_score is not None:
                actual_map[key] = float(row.actual_score)

    # Predict target keys using custom KNN predictor (distance-weighted, per-subject)
    predictions: Dict[str, float] = {}
    if dataset and actual_map and target_keys:
        # choose neighbor count based on reference sample size
        n_samples = len(dataset)
        k_neighbors = min(10, max(1, n_samples))
        predictions = _predict_with_knn_per_subject(dataset, actual_map, target_keys, k=k_neighbors)

    for idx, key in enumerate(feature_keys):
        row = row_by_key.get(key)
        if not row:
            # create missing StudyScore rows for future predictions
            subj, sem, gr = key.split("|")
            row = models.StudyScore(
                user_id=user_id,
                grade_level=gr,
                semester=sem,
                subject=subj,
            )
            db.add(row)
            row_by_key[key] = row

        # determine if this key is in future (after current_idx)
        is_future = False
        if current_idx is None:
            # if no current grade set, treat missing actuals as candidates for prediction
            is_future = row.actual_score is None
        else:
            is_future = idx > current_idx

        if is_future:
            # Use the custom KNN predictor results first (distance-weighted)
            pred_val = predictions.get(key) if predictions else None

            # Fallback to baseline if needed
            if pred_val is None:
                pred_val = baseline_preds.get(key)

            if pred_val is None:
                continue

            pred_val = float(pred_val)
            if (
                row.predicted_score != pred_val
                or row.predicted_source != "knn_predictor"
                or row.predicted_status != "generated"
            ):
                row.predicted_score = pred_val
                row.predicted_source = "knn_predictor"
                row.predicted_status = "generated"
                row.predicted_updated_at = timestamp
                results.append(row)
        else:
            # not future: ensure we do not keep stray predictions for known actuals
            if row.actual_score is not None and row.predicted_score is not None:
                row.predicted_score = None
                row.predicted_source = None
                row.predicted_status = None
                row.predicted_updated_at = None
                results.append(row)

    return results

