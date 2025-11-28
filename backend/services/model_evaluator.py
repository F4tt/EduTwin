"""
Model Evaluation Service
Evaluates KNN, Kernel Regression, and LWLR models on two prediction tasks:
1. Predict grade 12 from grades 10-11
2. Predict grade 11 from grade 10

Uses 80/20 train-test split and calculates MAE, MSE, RMSE, and accuracy metrics.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from scipy.spatial.distance import euclidean
from sklearn.linear_model import LinearRegression
import pandas as pd

from db import models
from ml.knn_common import build_feature_key, split_feature_key
from core.study_constants import SUBJECTS


def _load_reference_dataset(db) -> List[Dict[str, float]]:
    """Load all KNN reference samples from database (shared dataset)."""
    samples = db.query(models.KNNReferenceSample).all()
    dataset: List[Dict[str, float]] = []
    for sample in samples:
        feature_map = sample.feature_data or {}
        if feature_map:
            dataset.append({k: float(v) for k, v in feature_map.items() if isinstance(v, (int, float))})
    return dataset


def _prepare_evaluation_dataset(
    dataset: List[Dict[str, float]],
    input_grades: List[str],
    target_grade: str,
) -> Tuple[List[Dict], List[str], List[str]]:
    """
    Prepare dataset for evaluation task.
    Returns: (data_with_valid_pairs, input_keys, target_keys)
    """
    input_keys = []
    target_keys = []

    # Build feature keys for input grades
    for grade in input_grades:
        for subject in SUBJECTS:
            input_keys.append(build_feature_key(subject, "1", grade))  # semester 1
            input_keys.append(build_feature_key(subject, "2", grade))  # semester 2

    # Build feature keys for target grade
    for subject in SUBJECTS:
        target_keys.append(build_feature_key(subject, "1", target_grade))
        target_keys.append(build_feature_key(subject, "2", target_grade))

    # Filter dataset: keep only samples that have ALL input and target keys
    valid_data = []
    for sample in dataset:
        if all(k in sample and sample[k] is not None for k in input_keys) and \
           all(k in sample and sample[k] is not None for k in target_keys):
            valid_data.append(sample)

    return valid_data, input_keys, target_keys


def _predict_with_knn(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    k: int = 5,
) -> np.ndarray:
    """KNN prediction using distance-weighted voting."""
    predictions = []
    for x_test_point in X_test:
        # Compute distances to all training points
        distances = np.linalg.norm(X_train - x_test_point, axis=1)
        # Get top k nearest indices
        top_k_indices = np.argsort(distances)[:k]
        top_k_distances = distances[top_k_indices]
        top_k_values = y_train[top_k_indices]

        # Distance-weighted average
        weights = np.where(top_k_distances == 0, 1.0, 1.0 / (top_k_distances + 1e-6))
        weighted_avg = np.sum(weights * top_k_values) / np.sum(weights)
        predictions.append(weighted_avg)

    return np.array(predictions)


def _predict_with_kernel_regression(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    bandwidth: float = 1.25,
) -> np.ndarray:
    """Kernel Regression using Gaussian kernel."""
    predictions = []

    # Use provided bandwidth (sigma)
    sigma = bandwidth

    for x_test_point in X_test:
        numerator = 0.0
        denominator = 0.0

        for x_train_point, y_train_value in zip(X_train, y_train):
            distance = euclidean(x_test_point, x_train_point)
            # Gaussian kernel weight
            weight = np.exp(-(distance ** 2) / (2 * sigma ** 2))
            numerator += weight * y_train_value
            denominator += weight

        if denominator > 0:
            predictions.append(numerator / denominator)
        else:
            predictions.append(np.mean(y_train))

    return np.array(predictions)


def _predict_with_lwlr(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    tau: float = 3.0,
) -> np.ndarray:
    """Locally Weighted Linear Regression."""
    predictions = []

    for x_test_point in X_test:
        # Compute distances to all training points
        distances = np.linalg.norm(X_train - x_test_point, axis=1)

        # Determine bandwidth for tricube weight function using tau parameter
        max_distance = np.max(distances)
        bandwidth = max(max_distance / tau, 0.1)

        # Tricube weights
        normalized_distances = distances / bandwidth
        weights = np.zeros_like(normalized_distances)
        mask = normalized_distances < 1.0
        weights[mask] = (1.0 - normalized_distances[mask] ** 3) ** 3
        weights[~mask] = 0.01  # Small weight for distant points

        # Weighted linear regression
        try:
            lr = LinearRegression()
            lr.fit(X_train, y_train, sample_weight=weights)
            pred = lr.predict([x_test_point])[0]
            predictions.append(pred)
        except Exception:
            predictions.append(np.mean(y_train))

    return np.array(predictions)


def _calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calculate MAE, MSE, RMSE, and accuracy metrics."""
    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)

    # Accuracy: percentage of predictions within 0.5 points (on 10-point scale)
    # accuracy = (max_error / 10) -> inverted to percentage
    # Or: accuracy = 100 * (1 - mae/10) but capped at 100
    # Better: accuracy = 100 - (mae/10)*100, clamped to [0, 100]
    accuracy = max(0, min(100, 100 - (mae / 10) * 100))

    return {
        "mae": round(mae, 4),
        "mse": round(mse, 4),
        "rmse": round(rmse, 4),
        "accuracy": round(accuracy, 2),
    }


def evaluate_all_models(db) -> Dict:
    """
    Evaluate all three models on both prediction tasks.
    Uses shared reference dataset (managed by admin/developer).
    
    Tasks:
    1. Predict grade 12 from grades 10-11 (all subjects)
    2. Predict grade 11 from grade 10 (all subjects)
    
    Returns:
    {
        "task_1": {  # Predict grade 12 from 10-11
            "knn": {mae, mse, rmse, accuracy},
            "kernel_regression": {...},
            "lwlr": {...}
        },
        "task_2": {  # Predict grade 11 from 10
            "knn": {...},
            "kernel_regression": {...},
            "lwlr": {...}
        },
        "recommendation": "Model1, Model2 (best performing)",
        "best_accuracy": 95.5
    }
    """

    # Load model parameters from database
    params = db.query(models.ModelParameters).first()
    if not params:
        params = models.ModelParameters(knn_n=15, kr_bandwidth=1.25, lwlr_tau=3.0)
        db.add(params)
        db.commit()
        db.refresh(params)

    knn_n = params.knn_n
    kr_bandwidth = params.kr_bandwidth
    lwlr_tau = params.lwlr_tau

    # Load reference dataset (shared across all users)
    dataset = _load_reference_dataset(db)
    if not dataset or len(dataset) < 20:
        return {
            "error": "Không đủ dữ liệu tham chiếu để đánh giá. Cần ít nhất 20 mẫu.",
        }

    results = {
        "task_1": {},  # Predict 12 from 10-11
        "task_2": {},  # Predict 11 from 10
    }

    # Task 1: Predict grade 12 from grades 10-11
    print(f"[EVAL] Task 1: Predicting grade 12 from grades 10-11 (n={knn_n}, bandwidth={kr_bandwidth}, tau={lwlr_tau})")
    data_1, input_keys_1, target_keys_1 = _prepare_evaluation_dataset(
        dataset, input_grades=["10", "11"], target_grade="12"
    )
    if len(data_1) >= 20:
        # Prepare data matrix
        df_1 = pd.DataFrame(data_1)
        X_1 = df_1[input_keys_1].values.astype(float)
        y_1 = df_1[target_keys_1].values.astype(float).mean(axis=1)  # Average across subjects

        # 80/20 split
        X_train_1, X_test_1, y_train_1, y_test_1 = train_test_split(
            X_1, y_1, test_size=0.2, random_state=42
        )

        # Evaluate KNN
        try:
            k = min(knn_n, len(X_train_1) - 1)
            y_pred_knn_1 = _predict_with_knn(X_train_1, y_train_1, X_test_1, k=k)
            results["task_1"]["knn"] = _calculate_metrics(y_test_1, y_pred_knn_1)
        except Exception as e:
            print(f"[EVAL] KNN Task 1 error: {e}")
            results["task_1"]["knn"] = None

        # Evaluate Kernel Regression
        try:
            y_pred_kr_1 = _predict_with_kernel_regression(X_train_1, y_train_1, X_test_1, bandwidth=kr_bandwidth)
            results["task_1"]["kernel_regression"] = _calculate_metrics(y_test_1, y_pred_kr_1)
        except Exception as e:
            print(f"[EVAL] Kernel Regression Task 1 error: {e}")
            results["task_1"]["kernel_regression"] = None

        # Evaluate LWLR
        try:
            y_pred_lwlr_1 = _predict_with_lwlr(X_train_1, y_train_1, X_test_1, tau=lwlr_tau)
            results["task_1"]["lwlr"] = _calculate_metrics(y_test_1, y_pred_lwlr_1)
        except Exception as e:
            print(f"[EVAL] LWLR Task 1 error: {e}")
            results["task_1"]["lwlr"] = None
    else:
        results["error"] = f"Task 1: Không đủ mẫu hợp lệ (cần >=20, có {len(data_1)})"
        return results

    # Task 2: Predict grade 11 from grade 10
    print(f"[EVAL] Task 2: Predicting grade 11 from grade 10")
    data_2, input_keys_2, target_keys_2 = _prepare_evaluation_dataset(
        dataset, input_grades=["10"], target_grade="11"
    )
    if len(data_2) >= 20:
        df_2 = pd.DataFrame(data_2)
        X_2 = df_2[input_keys_2].values.astype(float)
        y_2 = df_2[target_keys_2].values.astype(float).mean(axis=1)

        X_train_2, X_test_2, y_train_2, y_test_2 = train_test_split(
            X_2, y_2, test_size=0.2, random_state=42
        )

        # Evaluate KNN
        try:
            k = min(knn_n, len(X_train_2) - 1)
            y_pred_knn_2 = _predict_with_knn(X_train_2, y_train_2, X_test_2, k=k)
            results["task_2"]["knn"] = _calculate_metrics(y_test_2, y_pred_knn_2)
        except Exception as e:
            print(f"[EVAL] KNN Task 2 error: {e}")
            results["task_2"]["knn"] = None

        # Evaluate Kernel Regression
        try:
            y_pred_kr_2 = _predict_with_kernel_regression(X_train_2, y_train_2, X_test_2, bandwidth=kr_bandwidth)
            results["task_2"]["kernel_regression"] = _calculate_metrics(y_test_2, y_pred_kr_2)
        except Exception as e:
            print(f"[EVAL] Kernel Regression Task 2 error: {e}")
            results["task_2"]["kernel_regression"] = None

        # Evaluate LWLR
        try:
            y_pred_lwlr_2 = _predict_with_lwlr(X_train_2, y_train_2, X_test_2, tau=lwlr_tau)
            results["task_2"]["lwlr"] = _calculate_metrics(y_test_2, y_pred_lwlr_2)
        except Exception as e:
            print(f"[EVAL] LWLR Task 2 error: {e}")
            results["task_2"]["lwlr"] = None
    else:
        results["error"] = f"Task 2: Không đủ mẫu hợp lệ (cần >=20, có {len(data_2)})"
        return results

    # Calculate recommendation based on best accuracy across both tasks
    all_accuracies = []
    for task_name in ["task_1", "task_2"]:
        for model_name in ["knn", "kernel_regression", "lwlr"]:
            if model_name in results[task_name] and results[task_name][model_name]:
                acc = results[task_name][model_name]["accuracy"]
                all_accuracies.append((model_name, acc))

    if all_accuracies:
        # Sort by accuracy descending
        all_accuracies.sort(key=lambda x: x[1], reverse=True)

        # Find best accuracy
        best_acc = all_accuracies[0][1]

        # Get only the first (best) model
        best_model = all_accuracies[0][0]

        # Format model names for display
        display_names = {
            "knn": "KNN",
            "kernel_regression": "Kernel Regression",
            "lwlr": "LWLR"
        }
        recommendation = display_names.get(best_model, best_model)

        results["recommendation"] = recommendation
        results["best_accuracy"] = round(best_acc, 2)
    else:
        results["recommendation"] = "Không thể xác định (lỗi đánh giá)"
        results["best_accuracy"] = None

    results["dataset_size"] = len(dataset)
    results["task_1_samples"] = len(data_1)
    results["task_2_samples"] = len(data_2)
    # Add train/test split info (80/20)
    results["task_1_train_samples"] = int(len(data_1) * 0.8)
    results["task_1_test_samples"] = int(len(data_1) * 0.2)
    results["task_2_train_samples"] = int(len(data_2) * 0.8)
    results["task_2_test_samples"] = int(len(data_2) * 0.2)
    results["parameters"] = {
        "knn_n": knn_n,
        "kr_bandwidth": kr_bandwidth,
        "lwlr_tau": lwlr_tau
    }

    return results
