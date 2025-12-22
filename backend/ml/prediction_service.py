"""
Custom Prediction Service
Handles predictions for custom teaching structures using shared ML models and parameters
"""

from typing import Dict, List, Set, Tuple
from math import sqrt
from sqlalchemy.orm import Session
import numpy as np

from db import models


def _predict_with_knn(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    k: int = 5,
) -> Dict[str, float]:
    """KNN prediction for custom structure"""
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


def _predict_with_kernel_regression(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    bandwidth: float = 1.0,
) -> Dict[str, float]:
    """Kernel Regression prediction for custom structure"""
    if not dataset or not actual_map or not target_keys:
        return {}

    actual_keys = set(actual_map.keys())
    predictions: Dict[str, float] = {}

    for target_key in target_keys:
        numerator = 0.0
        denominator = 0.0

        for sample in dataset:
            overlap = actual_keys & sample.keys()
            if not overlap:
                continue

            # Calculate distance
            distance_sq = 0.0
            for key in overlap:
                diff = sample[key] - actual_map[key]
                distance_sq += diff * diff
            distance = sqrt(distance_sq)

            # Gaussian kernel
            weight = np.exp(-(distance ** 2) / (2 * bandwidth ** 2))

            value = sample.get(target_key)
            if value is not None:
                numerator += weight * value
                denominator += weight

        if denominator > 0:
            predictions[target_key] = round(numerator / denominator, 2)

    return predictions


def _predict_with_lwlr(
    dataset: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    tau: float = 1.0,
) -> Dict[str, float]:
    """Locally Weighted Linear Regression prediction for custom structure"""
    if not dataset or not actual_map or not target_keys:
        return {}

    actual_keys = set(actual_map.keys())
    predictions: Dict[str, float] = {}

    # Get common features
    common_features = actual_keys
    for sample in dataset:
        common_features = common_features & set(sample.keys())
    
    if not common_features:
        return {}

    common_features = sorted(common_features)

    for target_key in target_keys:
        # Build training data
        X_train = []
        y_train = []

        for sample in dataset:
            if target_key not in sample:
                continue
            x = [sample[f] for f in common_features if f in sample]
            if len(x) == len(common_features):
                X_train.append(x)
                y_train.append(sample[target_key])

        if len(X_train) < 2:
            continue

        X_train = np.array(X_train)
        y_train = np.array(y_train)
        x_query = np.array([actual_map[f] for f in common_features])

        # Calculate weights
        distances = np.linalg.norm(X_train - x_query, axis=1)
        weights = np.exp(-(distances ** 2) / (2 * tau ** 2))
        W = np.diag(weights)

        # Weighted linear regression
        try:
            X_train_bias = np.c_[np.ones(X_train.shape[0]), X_train]
            x_query_bias = np.r_[1, x_query]
            
            XtWX = X_train_bias.T @ W @ X_train_bias
            XtWy = X_train_bias.T @ W @ y_train
            
            theta = np.linalg.solve(XtWX, XtWy)
            pred = x_query_bias @ theta
            
            predictions[target_key] = round(float(pred), 2)
        except np.linalg.LinAlgError:
            continue

    return predictions


def update_predictions_for_custom_structure(
    db: Session,
    user_id: int,
    structure_id: int,
    current_time_point: str,
    active_model: str,
    model_params: Dict[str, float]
) -> int:
    """
    Update predictions for a custom structure
    
    Args:
        db: Database session
        user_id: User ID
        structure_id: Custom structure ID
        current_time_point: Current time point label
        active_model: Active ML model (knn, kernel_regression, lwlr)
        model_params: Dict with model parameters (knn_n, kr_bandwidth, lwlr_tau)
    
    Returns:
        Number of predictions made
    """
    # Get structure
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        return 0
    
    # Load reference dataset for this structure
    reference_samples = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).all()
    
    if not reference_samples:
        return 0
    
    dataset: List[Dict[str, float]] = []
    for sample in reference_samples:
        if sample.score_data:
            dataset.append({k: float(v) for k, v in sample.score_data.items() if isinstance(v, (int, float))})
    
    if not dataset:
        return 0
    
    # Get current time point index
    try:
        current_tp_index = structure.time_point_labels.index(current_time_point)
    except ValueError:
        return 0
    
    # Load user's actual scores
    user_scores = db.query(models.CustomUserScore).filter(
        models.CustomUserScore.user_id == user_id,
        models.CustomUserScore.structure_id == structure_id
    ).all()
    
    # Build score lookup and ensure all slots exist
    score_by_key: Dict[str, models.CustomUserScore] = {}
    
    for score in user_scores:
        key = f"{score.subject}_{score.time_point}"
        score_by_key[key] = score
    
    # Create missing score records for all slots
    for i, tp in enumerate(structure.time_point_labels):
        for subject in structure.subject_labels:
            key = f"{subject}_{tp}"
            if key not in score_by_key:
                new_score = models.CustomUserScore(
                    user_id=user_id,
                    structure_id=structure_id,
                    subject=subject,
                    time_point=tp
                )
                db.add(new_score)
                score_by_key[key] = new_score
    
    db.commit()
    
    # Refresh all score records
    user_scores = db.query(models.CustomUserScore).filter(
        models.CustomUserScore.user_id == user_id,
        models.CustomUserScore.structure_id == structure_id
    ).all()
    
    score_by_key = {}
    for score in user_scores:
        key = f"{score.subject}_{score.time_point}"
        score_by_key[key] = score
    
    # Build ordered feature keys
    ordered_keys = []
    for tp in structure.time_point_labels:
        for subject in structure.subject_labels:
            ordered_keys.append(f"{subject}_{tp}")
    
    # Separate input keys (≤ current) and target keys (> current)
    input_keys = []
    target_keys = set()
    missing_current_keys = set()
    
    for i, tp in enumerate(structure.time_point_labels):
        for subject in structure.subject_labels:
            key = f"{subject}_{tp}"
            if i <= current_tp_index:
                input_keys.append(key)
                # Track keys with missing actual scores
                if score_by_key[key].actual_score is None:
                    missing_current_keys.add(key)
            else:
                target_keys.add(key)
    
    # Add missing current keys to prediction targets
    target_keys = target_keys | missing_current_keys
    
    # Use KNNImputer to fill missing values in input keys (≤ current_time_point)
    actual_map: Dict[str, float] = {}
    
    if input_keys and dataset:
        import pandas as pd
        from sklearn.impute import KNNImputer
        
        # Build reference dataframe from dataset
        ref_data = []
        for sample in dataset:
            row_data = []
            for key in input_keys:
                row_data.append(sample.get(key, np.nan))
            ref_data.append(row_data)
        
        df_ref = pd.DataFrame(ref_data, columns=input_keys)
        
        # Build user's input row
        user_input_row = []
        for key in input_keys:
            score_val = score_by_key[key].actual_score
            user_input_row.append(score_val if score_val is not None else np.nan)
        
        try:
            ref_matrix = df_ref.to_numpy(dtype=float)
            user_inputs = np.array(user_input_row, dtype=float)
            
            n_samples = ref_matrix.shape[0] if ref_matrix.size > 0 else 0
            n_neighbors = min(10, max(1, n_samples)) if n_samples > 0 else 1
            
            imputer = KNNImputer(n_neighbors=n_neighbors)
            stacked = np.vstack([ref_matrix, user_inputs]) if n_samples > 0 else user_inputs.reshape(1, -1)
            
            imputed = imputer.fit_transform(stacked)
            user_imputed_inputs = imputed[-1]
            
            # Fill actual_map with imputed values AND save imputed values to database
            for i, key in enumerate(input_keys):
                val = user_imputed_inputs[i]
                if not pd.isna(val):
                    actual_map[key] = float(val)
                    
                    # Save imputed value to database if it was missing
                    if key in score_by_key:
                        score_record = score_by_key[key]
                        # Only save as predicted if actual_score is None (was imputed)
                        if score_record.actual_score is None:
                            score_record.predicted_score = float(val)
                            score_record.predicted_source = "knn_imputer"
                            score_record.predicted_status = "imputed"
        except Exception as e:
            # Fallback: use only existing actual scores
            for key in input_keys:
                score_val = score_by_key[key].actual_score
                if score_val is not None:
                    actual_map[key] = float(score_val)
    else:
        # No imputation possible; use existing actuals only
        for key in input_keys:
            score_val = score_by_key[key].actual_score
            if score_val is not None:
                actual_map[key] = float(score_val)
    
    # Determine target keys (future time points)
    target_keys: Set[str] = set()
    for i, tp in enumerate(structure.time_point_labels):
        if i > current_tp_index:
            for subject in structure.subject_labels:
                key = f"{subject}_{tp}"
                target_keys.add(key)
    
    # Also predict missing current keys
    target_keys = target_keys | missing_current_keys
    
    if not target_keys or not actual_map:
        return 0
    
    # Select prediction function
    if active_model == "kernel_regression":
        predictions = _predict_with_kernel_regression(
            dataset=dataset,
            actual_map=actual_map,
            target_keys=target_keys,
            bandwidth=model_params["kr_bandwidth"]
        )
    elif active_model == "lwlr":
        predictions = _predict_with_lwlr(
            dataset=dataset,
            actual_map=actual_map,
            target_keys=target_keys,
            tau=model_params["lwlr_tau"]
        )
    else:
        # Default to KNN
        predictions = _predict_with_knn(
            dataset=dataset,
            actual_map=actual_map,
            target_keys=target_keys,
            k=model_params["knn_n"]
        )
    
    # Note: predictions are already in the scale of the reference dataset
    
    # Save predictions
    predicted_count = 0
    for key, pred_value in predictions.items():
        if key in score_by_key:
            score_record = score_by_key[key]
            score_record.predicted_score = pred_value
            score_record.predicted_source = active_model
            score_record.predicted_status = "active"
            predicted_count += 1
    
    db.commit()
    
    return predicted_count
