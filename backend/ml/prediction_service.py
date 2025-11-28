from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import sqrt
from statistics import mean
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
import numpy as np
from sklearn.linear_model import LinearRegression
from scipy.spatial.distance import euclidean

from db import models
from ml.knn_common import build_feature_key


def _load_reference_dataset(db: Session) -> List[Dict[str, float]]:
    """Load reference dataset (shared across all users)."""
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


def _predict_with_kernel_regression(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    k: int = 5,
    bandwidth: float = 1.25,
) -> Dict[str, float]:
    """
    Predict using Nadaraya-Watson kernel regression with Gaussian kernel.
    Similar output as KNN but uses all samples with kernel-weighted distances.
    
    Args:
        bandwidth: Gaussian kernel bandwidth (sigma) parameter
    """
    if not dataset or not actual_map or not target_keys:
        return {}

    predictions: Dict[str, float] = {}
    actual_keys = set(actual_map.keys())
    actual_vec = np.array([actual_map[k] for k in sorted(actual_keys)], dtype=float)
    
    # Use provided bandwidth (sigma) for Gaussian kernel
    sigma = bandwidth

    for target_key in target_keys:
        numerator = 0.0
        denominator = 0.0

        for sample in dataset:
            overlap = actual_keys & sample.keys()
            if not overlap:
                continue

            # Compute Euclidean distance
            sample_vec = np.array([sample[k] for k in sorted(actual_keys)], dtype=float)
            distance = euclidean(actual_vec, sample_vec)

            # Gaussian kernel weight
            weight = np.exp(-(distance ** 2) / (2 * sigma ** 2))

            value = sample.get(target_key)
            if value is not None and weight > 0:
                numerator += weight * value
                denominator += weight

        if denominator > 0:
            predictions[target_key] = round(numerator / denominator, 2)

    return predictions


def _predict_with_lwlr(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    k: int = 5,
    tau: float = 3.0,
) -> Dict[str, float]:
    """
    Predict using Locally Weighted Linear Regression (LWLR).
    For each target key, fit a weighted linear regression on k nearest neighbors.
    
    Args:
        tau: Controls window size for tricube kernel (higher = wider window)
    """
    if not dataset or not actual_map or not target_keys:
        return {}

    predictions: Dict[str, float] = {}
    actual_keys = sorted(actual_map.keys())
    actual_vec = np.array([actual_map[k] for k in actual_keys], dtype=float)

    for target_key in target_keys:
        # Find neighbors that have this target key
        neighbors_with_target: List[Tuple[float, Dict[str, float]]] = []

        for sample in dataset:
            overlap = set(actual_keys) & sample.keys()
            if not overlap or target_key not in sample:
                continue

            # Compute distance
            sample_vec = np.array([sample[k] for k in actual_keys], dtype=float)
            distance = euclidean(actual_vec, sample_vec)
            neighbors_with_target.append((distance, sample))

        if len(neighbors_with_target) < 2:
            # Need at least 2 neighbors for linear regression
            continue

        # Sort by distance and keep top k
        neighbors_with_target.sort(key=lambda x: x[0])
        top_neighbors = neighbors_with_target[: k if k > 0 else len(neighbors_with_target)]

        # Compute bandwidth for distance-based weighting using tau parameter
        max_distance = top_neighbors[-1][0]
        bandwidth = max(max_distance / tau, 0.1)

        # Extract X matrix and y vector
        X_data = []
        y_data = []
        sample_weights = []

        for distance, sample in top_neighbors:
            sample_vec = np.array([sample.get(key, 0.0) for key in actual_keys], dtype=float)
            X_data.append(sample_vec)
            y_data.append(sample[target_key])

            # Tricube weight function: (1 - (d/bandwidth)^3)^3
            normalized_dist = distance / bandwidth
            if normalized_dist < 1.0:
                weight = (1.0 - normalized_dist ** 3) ** 3
            else:
                weight = 0.0
            sample_weights.append(max(weight, 0.01))  # Ensure non-zero weight

        if len(X_data) >= 2:
            try:
                X_array = np.array(X_data, dtype=float)
                y_array = np.array(y_data, dtype=float)
                weights_array = np.array(sample_weights, dtype=float)

                # Fit weighted linear regression
                lr = LinearRegression()
                lr.fit(X_array, y_array, sample_weight=weights_array)

                # Predict for actual user's input vector
                predicted = lr.predict([actual_vec])[0]
                predictions[target_key] = round(float(predicted), 2)
            except Exception:
                # If regression fails, skip this target
                continue

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
    import pandas as pd

    results: List[models.StudyScore] = []
    scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    if not scores:
        return results

    has_reference_dataset = db.query(models.KNNReferenceSample).count() > 0

    if not has_reference_dataset:
        print(f"[PREDICTION] No reference dataset found for predictions")
        for row in scores:
            if row.predicted_score is not None:
                row.predicted_score = None
                row.predicted_source = None
                row.predicted_status = None
                row.predicted_updated_at = None
                results.append(row)
        return results

    # Query active ML model from config
    model_config = db.query(models.MLModelConfig).first()
    active_model = model_config.active_model if model_config else "knn"

    # Query model parameters
    model_params = db.query(models.ModelParameters).first()
    if not model_params:
        model_params = models.ModelParameters(knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
        db.add(model_params)
        db.commit()
        db.refresh(model_params)

    knn_n = model_params.knn_n
    kr_bandwidth = model_params.kr_bandwidth
    lwlr_tau = model_params.lwlr_tau

    # Select prediction function based on active model
    if active_model == "kernel_regression":
        predictor_func = _predict_with_kernel_regression
    elif active_model == "lwlr":
        predictor_func = _predict_with_lwlr
    else:
        # Default to KNN for backward compatibility
        predictor_func = _predict_with_knn_per_subject

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

    # Map existing scores - query all existing scores for this user to avoid duplicates
    row_by_key: Dict[str, models.StudyScore] = {}
    for score in scores:
        key = build_feature_key(score.subject, score.semester, score.grade_level)
        row_by_key[key] = score
    
    # Also query all existing StudyScores from database to ensure we don't create duplicates
    all_existing_scores = (
        db.query(models.StudyScore)
        .filter(models.StudyScore.user_id == user_id)
        .all()
    )
    for existing_score in all_existing_scores:
        key = build_feature_key(existing_score.subject, existing_score.semester, existing_score.grade_level)
        if key not in row_by_key:
            row_by_key[key] = existing_score

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

    # Threshold check: if actual_count < 5, skip prediction entirely
    if actual_count < 5:
        print(f"[PREDICTION] User {user_id} has only {actual_count} actual scores (need 5+). Skipping predictions.")
        # No prediction; only return existing scores without predictions
        return results

    # Build dataset matrix from reference samples
    dataset = _load_reference_dataset(db)
    print(f"[PREDICTION] Loaded {len(dataset) if dataset else 0} reference samples for user {user_id}")
    # columns = feature_keys

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
    # current grade) we'll use the selected predictor function to produce predictions.
    timestamp = datetime.utcnow()

    # Precompute baseline predictions to use as fallback when model predictions are missing
    baseline_preds = _baseline_predictions(scores, target_keys=set(feature_keys)) if dataset else {}

    # Determine input and target key sets based on current_idx
    missing_current_keys: Set[str] = set()
    if current_idx is not None:
        input_keys = feature_keys[: current_idx + 1]
        missing_current_keys = {
            key for key in input_keys
            if not (row_by_key.get(key) and row_by_key[key].actual_score is not None)
        }
        target_keys = set(feature_keys[current_idx + 1 :]) | missing_current_keys
    else:
        # If no current grade, treat existing actuals as inputs and the rest as targets
        input_keys = [k for k in feature_keys if row_by_key.get(k) and row_by_key[k].actual_score is not None]
        target_keys = set(k for k in feature_keys if k not in input_keys)
        missing_current_keys = set()

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

    # Predict target keys using selected model predictor
    predictions: Dict[str, float] = {}
    if dataset and actual_map and target_keys:
        # choose neighbor count based on reference sample size
        n_samples = len(dataset)
        k_neighbors = min(knn_n, max(1, n_samples))
        
        # Call predictor with appropriate parameters
        if active_model == "kernel_regression":
            predictions = predictor_func(dataset, actual_map, target_keys, k=k_neighbors, bandwidth=kr_bandwidth)
        elif active_model == "lwlr":
            predictions = predictor_func(dataset, actual_map, target_keys, k=k_neighbors, tau=lwlr_tau)
        else:
            # KNN doesn't use extra parameters beyond k
            predictions = predictor_func(dataset, actual_map, target_keys, k=k_neighbors)

    for idx, key in enumerate(feature_keys):
        row = row_by_key.get(key)
        if not row:
            # create missing StudyScore rows for future predictions
            subj, sem, gr = key.split("|")
            # Check if it already exists in database or session to avoid duplicate key error
            existing = (
                db.query(models.StudyScore)
                .filter(
                    models.StudyScore.user_id == user_id,
                    models.StudyScore.subject == subj,
                    models.StudyScore.semester == sem,
                    models.StudyScore.grade_level == gr,
                )
                .first()
            )
            if existing:
                row = existing
            else:
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

        needs_current_backfill = current_idx is not None and key in missing_current_keys

        if is_future or needs_current_backfill:
            # Use the model predictor results first
            pred_val = predictions.get(key) if predictions else None

            # Fallback to baseline if needed
            if pred_val is None:
                pred_val = baseline_preds.get(key)

            if pred_val is None and needs_current_backfill:
                # as a last resort, use the imputed value from actual_map (if available)
                if key in actual_map:
                    pred_val = float(actual_map[key])

            if pred_val is None:
                continue

            pred_val = float(pred_val)
            source_label = active_model if is_future else f"{active_model}_current_backfill"
            if (
                row.predicted_score != pred_val
                or row.predicted_source != source_label
                or row.predicted_status != "generated"
            ):
                row.predicted_score = pred_val
                row.predicted_source = source_label
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

