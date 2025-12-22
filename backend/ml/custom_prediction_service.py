"""
Custom Prediction Service
Handles predictions for custom teaching structures using shared ML models and parameters
Supports both full dataset and cluster-based (fast) prediction modes
"""

from typing import Dict, List, Set, Tuple, Optional
from math import sqrt
from sqlalchemy.orm import Session
import numpy as np
import os

from db import models
from ml.cluster_prototype_service import (
    ClusterPrototypeIndex,
    build_cluster_index_for_structure,
    predict_with_cluster_index
)
from ml.prediction_cache import (
    get_cached_prediction,
    set_cached_prediction,
    invalidate_prediction_cache
)
from ml.scale_normalizer import get_scale_max


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
    
    # Calculate weights once for all target keys
    weights = []
    for sample in dataset:
        overlap = actual_keys & sample.keys()
        if not overlap:
            weights.append((0.0, sample))
            continue

        # Calculate distance
        distance_sq = 0.0
        for key in overlap:
            diff = sample[key] - actual_map[key]
            distance_sq += diff * diff
        distance = sqrt(distance_sq)

        # Gaussian kernel
        weight = np.exp(-(distance ** 2) / (2 * bandwidth ** 2))
        weights.append((weight, sample))
    
    # Predict each target key using pre-calculated weights
    predictions: Dict[str, float] = {}
    for target_key in target_keys:
        numerator = 0.0
        denominator = 0.0

        for weight, sample in weights:
            if weight == 0.0:
                continue
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
    model_params: Dict[str, float],
    use_clustering: bool = True
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
        use_clustering: Use cluster+prototype optimization (default True)
    
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
    
    # Note: dataset is already in the original scale from reference samples
    
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
    
    # Note: user's actual scores are already in the correct scale
    
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
    
    # Try to get cached predictions first
    cached_predictions = get_cached_prediction(
        user_id=user_id,
        structure_id=structure_id,
        current_time_point=current_time_point,
        actual_scores=actual_map,
        model_type=active_model,
        model_params=model_params
    )
    
    if cached_predictions:
        # Use cached results
        predictions = cached_predictions
        print(f"[PREDICT] Using cached predictions ({len(predictions)} values)")
    else:
        # Try to use clustering for faster prediction
        predictions = {}
        
        if use_clustering and len(dataset) >= 3000:
        # Use cluster+prototype approach for large datasets
            print(f"[PREDICT] Using cluster-based prediction (dataset size: {len(dataset)})")
        
        # Check if we have a cached index
        index_path = f"/tmp/cluster_index_{structure_id}.pkl"
        cluster_index = None
        
        if os.path.exists(index_path):
            try:
                cluster_index = ClusterPrototypeIndex.load(index_path)
                print(f"[PREDICT] Loaded cached cluster index")
            except:
                print(f"[PREDICT] Failed to load cached index, rebuilding...")
        
        if cluster_index is None:
            # Build new index with auto-calculated optimal parameters
            cluster_index = build_cluster_index_for_structure(
                db=db,
                structure_id=structure_id,
                n_clusters=None  # Auto-calculate based on dataset size
            )
            
            if cluster_index:
                # Cache it
                try:
                    cluster_index.save(index_path)
                    print(f"[PREDICT] Cached cluster index to {index_path}")
                except:
                    pass
        
        if cluster_index:
            predictions = predict_with_cluster_index(
                index=cluster_index,
                actual_map=actual_map,
                target_keys=target_keys,
                model_type=active_model,
                model_params=model_params
            )
    
    # Fallback to full dataset if clustering failed or disabled
    if not predictions:
        print(f"[PREDICT] Using full dataset prediction")
        
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
        
        # Cache the new predictions
        if predictions:
            set_cached_prediction(
                user_id=user_id,
                structure_id=structure_id,
                current_time_point=current_time_point,
                actual_scores=actual_map,
                model_type=active_model,
                model_params=model_params,
                predictions=predictions
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


def evaluate_models_for_structure(
    db: Session,
    structure_id: int,
    input_timepoints: List[str],
    output_timepoints: List[str],
    model_params: Dict[str, float]
) -> Dict:
    """
    Evaluate KNN, Kernel Regression, and LWLR models on custom structure.
    Uses 80/20 train-test split to predict output_timepoints from input_timepoints.
    
    NOTE: For large datasets (>= 3000 samples), delegates to cluster-based evaluation
    to match production prediction behavior exactly.
    """
    print(f"[EVALUATE] Starting evaluation for structure {structure_id}")
    print(f"[EVALUATE] Input timepoints: {input_timepoints}")
    print(f"[EVALUATE] Output timepoints: {output_timepoints}")
    
    # Try to get cached evaluation first
    from ml.prediction_cache import get_cached_evaluation, set_cached_evaluation
    
    cached_result = get_cached_evaluation(
        structure_id=structure_id,
        input_timepoints=input_timepoints,
        output_timepoints=output_timepoints,
        model_params=model_params,
        method="standard"
    )
    
    if cached_result:
        print(f"[EVALUATE] Using cached evaluation results")
        return cached_result
    
    # Get structure
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        return {"error": "Structure not found", "models": {}}
    
    # Load reference dataset
    samples = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).all()
    
    print(f"[EVALUATE] Found {len(samples)} reference samples")
    
    if not samples or len(samples) < 20:
        return {"error": "Cần ít nhất 20 mẫu để đánh giá", "models": {}}
    
    # Convert samples to dictionaries and filter valid samples
    dataset = []
    for sample in samples:
        dataset.append(sample.score_data)
    
    # Prepare input and output keys
    input_keys = []
    for subject in structure.subject_labels:
        for tp in input_timepoints:
            input_keys.append(f"{subject}_{tp}")
    
    output_keys = []
    for subject in structure.subject_labels:
        for tp in output_timepoints:
            output_keys.append(f"{subject}_{tp}")
    
    # Filter samples that have ALL input and output keys
    valid_samples = []
    for sample in dataset:
        if all(key in sample and sample[key] is not None for key in input_keys + output_keys):
            valid_samples.append(sample)
    
    print(f"[EVALUATE] Valid samples with all required data: {len(valid_samples)}")
    
    if len(valid_samples) < 20:
        return {"error": f"Chỉ có {len(valid_samples)} mẫu hợp lệ, cần ít nhất 20", "models": {}}
    
    # =========================================================================
    # DELEGATE TO CLUSTER-BASED EVALUATION FOR LARGE DATASETS
    # This ensures evaluation matches production prediction behavior
    # =========================================================================
    if len(valid_samples) >= 3000:
        print(f"[EVALUATE] Large dataset ({len(valid_samples)} >= 3000) - using cluster-based evaluation")
        from ml.cluster_prototype_service import evaluate_cluster_models
        
        result = evaluate_cluster_models(
            db=db,
            structure_id=structure_id,
            input_timepoints=input_timepoints,
            output_timepoints=output_timepoints,
            model_params=model_params,
            n_clusters=None,  # Auto-calculate
            prototypes_per_cluster=None  # Auto-calculate
        )
        
        # Add note that cluster method was used
        result["evaluation_method"] = "cluster_prototype"
        result["cluster_threshold"] = 3000
        
        # Cache with "standard" method key for compatibility
        set_cached_evaluation(
            structure_id=structure_id,
            input_timepoints=input_timepoints,
            output_timepoints=output_timepoints,
            model_params=model_params,
            method="standard",
            results=result
        )
        
        return result
    
    print(f"[EVALUATE] Small dataset ({len(valid_samples)} < 3000) - using full dataset evaluation")
    
    # Prepare X (input features) and y (output targets - averaged across subjects)
    X_data = []
    y_data = []
    
    for sample in valid_samples:
        # Extract input features
        x_row = [sample[key] for key in input_keys]
        X_data.append(x_row)
        
        # Extract output values and average them
        y_values = [sample[key] for key in output_keys]
        y_avg = sum(y_values) / len(y_values)
        y_data.append(y_avg)
    
    X = np.array(X_data)
    y = np.array(y_data)
    
    # 80/20 train-test split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"[EVALUATE] Train samples: {len(X_train)}, Test samples: {len(X_test)}")
    
    # Prepare models
    models_to_evaluate = {
        "knn": ("KNN", model_params["knn_n"]),
        "kernel_regression": ("Kernel Regression", model_params["kr_bandwidth"]),
        "lwlr": ("LWLR", model_params["lwlr_tau"])
    }
    
    results = {}
    
    for model_name, (display_name, param) in models_to_evaluate.items():
        print(f"[EVALUATE] Evaluating {display_name}...")
        
        try:
            if model_name == "knn":
                # KNN prediction
                predictions = []
                k = min(int(param), len(X_train) - 1)
                
                for x_test in X_test:
                    distances = np.linalg.norm(X_train - x_test, axis=1)
                    top_k_idx = np.argsort(distances)[:k]
                    top_k_dist = distances[top_k_idx]
                    top_k_vals = y_train[top_k_idx]
                    
                    weights = np.where(top_k_dist == 0, 1.0, 1.0 / (top_k_dist + 1e-6))
                    pred = np.sum(weights * top_k_vals) / np.sum(weights)
                    predictions.append(pred)
                
                y_pred = np.array(predictions)
                
            elif model_name == "kernel_regression":
                # Kernel Regression
                predictions = []
                bandwidth = param
                
                for x_test in X_test:
                    distances = np.linalg.norm(X_train - x_test, axis=1)
                    weights = np.exp(-(distances ** 2) / (2 * bandwidth ** 2))
                    
                    if np.sum(weights) > 0:
                        pred = np.sum(weights * y_train) / np.sum(weights)
                    else:
                        pred = np.mean(y_train)
                    predictions.append(pred)
                
                y_pred = np.array(predictions)
                
            else:  # lwlr
                # LWLR prediction
                from sklearn.linear_model import LinearRegression
                predictions = []
                tau = param
                
                for x_test in X_test:
                    distances = np.linalg.norm(X_train - x_test, axis=1)
                    max_dist = np.max(distances)
                    bandwidth = max(max_dist / tau, 0.1)
                    
                    norm_dist = distances / bandwidth
                    weights = np.zeros_like(norm_dist)
                    mask = norm_dist < 1.0
                    weights[mask] = (1.0 - norm_dist[mask] ** 3) ** 3
                    weights[~mask] = 0.01
                    
                    try:
                        lr = LinearRegression()
                        lr.fit(X_train, y_train, sample_weight=weights)
                        pred = lr.predict([x_test])[0]
                    except:
                        pred = np.mean(y_train)
                    
                    predictions.append(pred)
                
                y_pred = np.array(predictions)
            
            # Calculate metrics
            from sklearn.metrics import mean_absolute_error, mean_squared_error
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            
            # Calculate accuracy based on actual scale type
            scale_max = get_scale_max(getattr(structure, 'scale_type', '0-10'))
            accuracy = max(0, min(100, 100 - (mae / scale_max) * 100))
            
            print(f"[EVALUATE] {display_name}: MAE={mae:.4f}, RMSE={rmse:.4f}, Accuracy={accuracy:.2f}%")
            
            results[model_name] = {
                "mae": round(mae, 4),
                "mse": round(mse, 4),
                "rmse": round(rmse, 4),
                "accuracy": round(accuracy, 2),
                "test_samples": len(y_test)
            }
            
        except Exception as e:
            print(f"[EVALUATE] {display_name} error: {e}")
            results[model_name] = {"error": str(e)}
    
    print(f"[EVALUATE] Evaluation complete")
    
    # Calculate recommendation based on best accuracy
    best_model = None
    best_accuracy = 0
    
    for model_name, metrics in results.items():
        if "error" not in metrics and "accuracy" in metrics:
            if metrics["accuracy"] > best_accuracy:
                best_accuracy = metrics["accuracy"]
                best_model = model_name
    
    # Map model names to display names
    model_display_names = {
        "knn": "KNN",
        "kernel_regression": "Kernel Regression",
        "lwlr": "LWLR"
    }
    
    recommendation = model_display_names.get(best_model, "Không xác định") if best_model else "Không xác định"
    
    result = {
        "models": results,
        "recommendation": recommendation,
        "best_accuracy": round(best_accuracy, 2) if best_accuracy > 0 else None,
        "structure_name": structure.structure_name,
        "dataset_size": len(samples),
        "valid_samples": len(valid_samples),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "input_timepoints": input_timepoints,
        "output_timepoints": output_timepoints,
        "model_params": model_params
    }
    
    # Cache the evaluation result
    set_cached_evaluation(
        structure_id=structure_id,
        input_timepoints=input_timepoints,
        output_timepoints=output_timepoints,
        model_params=model_params,
        method="standard",
        results=result
    )
    
    return result

