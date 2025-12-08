"""
Clustering + Prototype Selection Service
Optimizes KNN/Kernel Regression/LWLR by:
1. Clustering data into K groups
2. Selecting prototypes within each cluster
3. Fast local prediction within assigned cluster
"""

from typing import Dict, List, Set, Tuple, Optional
from math import sqrt
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances_argmin_min
import pickle
from sqlalchemy.orm import Session

from db import models
from ml.prediction_cache import (
    get_cached_evaluation,
    set_cached_evaluation,
    invalidate_evaluation_cache,
    get_cached_cluster_index,
    set_cached_cluster_index,
    compute_dataset_hash,
    invalidate_cluster_cache
)


def calculate_optimal_clusters(dataset_size: int) -> int:
    """
    Calculate optimal number of clusters based on dataset size
    
    OPTIMIZED STRATEGY for LWLR accuracy:
    - Small (< 3,000): No clustering - use full dataset for maximum accuracy
    - Medium-Low (3,000 - 5,000): Light clustering (~15-22 clusters)
    - Medium (5,000 - 10,000): Moderate clustering (~30-45 clusters)
    - Large (10,000 - 30,000): Standard clustering (~50-100 clusters)
    - Very Large (30,000 - 50,000): Heavy clustering (~70-100 clusters)
    - Massive (> 50,000): Maximum clustering (100-150 clusters)
    """
    if dataset_size < 3000:
        # Small dataset: NO clustering, use full dataset for best LWLR accuracy
        return 1
    elif dataset_size < 5000:
        # Light clustering: ~15-22 clusters
        return max(15, int(np.sqrt(dataset_size / 10)))
    elif dataset_size < 10000:
        # Moderate clustering: ~30-45 clusters
        return max(30, int(np.sqrt(dataset_size / 5)))
    elif dataset_size < 30000:
        # Standard clustering: ~50-100 clusters
        return max(50, dataset_size // 300)
    elif dataset_size < 50000:
        # Heavy clustering: ~70-100 clusters
        return max(70, dataset_size // 500)
    else:
        # Maximum clustering: 100-150 clusters (capped)
        return min(150, max(100, dataset_size // 500))


def calculate_optimal_prototypes(cluster_size: int, total_dataset_size: int) -> int:
    """
    Calculate optimal number of prototypes per cluster
    
    OPTIMIZED for LWLR accuracy:
    - < 3,000: Use ALL samples (100%) - no reduction
    - 3,000 - 5,000: Keep 70-80% for high accuracy
    - 5,000 - 10,000: Keep 50-60% balanced approach
    - 10,000 - 30,000: Keep 35-45% for performance
    - > 30,000: Keep 25-35% prioritize speed
    
    LWLR requires sufficient samples for stable weighted regression.
    Minimum ~40-80 prototypes per cluster depending on dataset size.
    """
    if total_dataset_size < 3000:
        # Small dataset: use ALL samples for maximum accuracy
        return cluster_size
    elif total_dataset_size < 5000:
        # Keep 70-80% of cluster data
        n_prototypes = int(cluster_size * 0.75)
        return max(80, min(120, n_prototypes))
    elif total_dataset_size < 10000:
        # Keep 50-60% of cluster data
        n_prototypes = int(cluster_size * 0.55)
        return max(60, min(100, n_prototypes))
    elif total_dataset_size < 30000:
        # Keep 35-45% of cluster data
        n_prototypes = int(cluster_size * 0.4)
        return max(50, min(80, n_prototypes))
    else:
        # Keep 25-35% of cluster data for large datasets
        n_prototypes = int(cluster_size * 0.3)
        return max(40, min(60, n_prototypes))


class ClusterPrototypeIndex:
    """
    Maintains cluster centers and prototypes for fast prediction
    """
    
    def __init__(
        self,
        n_clusters: int = 50,
        prototypes_per_cluster: int = 20,
        random_state: int = 42
    ):
        """
        Args:
            n_clusters: Number of clusters (default 50)
            prototypes_per_cluster: Max prototypes per cluster (default 20)
            random_state: Random seed for reproducibility
        """
        self.n_clusters = n_clusters
        self.prototypes_per_cluster = prototypes_per_cluster
        self.random_state = random_state
        
        # Will be populated during fit()
        self.kmeans = None
        self.cluster_prototypes = {}  # cluster_id -> list of prototype samples
        self.feature_keys = []  # ordered feature names
        self.is_fitted = False
    
    def fit(self, dataset: List[Dict[str, float]], feature_keys: List[str]):
        """
        Cluster dataset and select prototypes
        
        Args:
            dataset: List of score dictionaries
            feature_keys: Ordered list of feature names (e.g., ['math_t1', 'science_t1', ...])
        """
        if not dataset or not feature_keys:
            raise ValueError("Dataset and feature_keys cannot be empty")
        
        self.feature_keys = feature_keys
        
        # Convert dataset to numpy array
        X = []
        valid_samples = []
        
        for sample in dataset:
            # Only use samples with all features present
            if all(key in sample and sample[key] is not None for key in feature_keys):
                row = [float(sample[key]) for key in feature_keys]
                X.append(row)
                valid_samples.append(sample)
        
        if len(X) < self.n_clusters:
            # If too few samples, use fewer clusters
            actual_clusters = max(1, len(X) // 5)
            print(f"[CLUSTER] Too few samples ({len(X)}), using {actual_clusters} clusters instead of {self.n_clusters}")
            self.n_clusters = actual_clusters
        
        X = np.array(X)
        
        # Fit KMeans
        print(f"[CLUSTER] Clustering {len(X)} samples into {self.n_clusters} clusters...")
        self.kmeans = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init=10
        )
        cluster_labels = self.kmeans.fit_predict(X)
        
        # Select prototypes for each cluster
        for cluster_id in range(self.n_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_samples = [valid_samples[i] for i in range(len(valid_samples)) if cluster_mask[i]]
            cluster_X = X[cluster_mask]
            
            if len(cluster_samples) == 0:
                continue
            
            # Calculate optimal prototypes for this cluster
            optimal_prototypes = calculate_optimal_prototypes(
                cluster_size=len(cluster_samples),
                total_dataset_size=len(X)
            )
            
            # Prototype selection: use k-medoids-like approach
            # Select points closest to cluster center
            center = self.kmeans.cluster_centers_[cluster_id:cluster_id+1]
            distances = np.linalg.norm(cluster_X - center, axis=1)
            
            # Take top N closest points as prototypes
            n_prototypes = min(optimal_prototypes, len(cluster_samples))
            prototype_indices = np.argsort(distances)[:n_prototypes]
            
            self.cluster_prototypes[cluster_id] = [cluster_samples[idx] for idx in prototype_indices]
            
            print(f"[CLUSTER] Cluster {cluster_id}: {len(cluster_samples)} samples -> {len(self.cluster_prototypes[cluster_id])} prototypes ({n_prototypes}/{len(cluster_samples)} = {100*n_prototypes/len(cluster_samples):.1f}%)")
        
        self.is_fitted = True
        total_prototypes = sum(len(p) for p in self.cluster_prototypes.values())
        reduction_ratio = 100 * (1 - total_prototypes / len(X))
        print(f"[CLUSTER] Clustering complete. Total prototypes: {total_prototypes}/{len(X)} (reduced by {reduction_ratio:.1f}%)")
    
    def assign_cluster(self, query_features: Dict[str, float]) -> int:
        """
        Assign query to nearest cluster based on cluster centers
        
        Args:
            query_features: Dict of feature values
            
        Returns:
            cluster_id
        """
        if not self.is_fitted:
            raise RuntimeError("Index not fitted. Call fit() first.")
        
        # Convert query to vector
        query_vector = np.array([query_features.get(key, 0.0) for key in self.feature_keys])
        
        # Find nearest cluster center
        cluster_id = self.kmeans.predict([query_vector])[0]
        
        return cluster_id
    
    def get_cluster_prototypes(self, cluster_id: int) -> List[Dict[str, float]]:
        """
        Get prototypes for a specific cluster
        
        Args:
            cluster_id: Cluster ID
            
        Returns:
            List of prototype samples
        """
        return self.cluster_prototypes.get(cluster_id, [])
    
    def save(self, filepath: str):
        """Save index to file"""
        data = {
            'kmeans': self.kmeans,
            'cluster_prototypes': self.cluster_prototypes,
            'feature_keys': self.feature_keys,
            'n_clusters': self.n_clusters,
            'prototypes_per_cluster': self.prototypes_per_cluster,
            'is_fitted': self.is_fitted
        }
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    @classmethod
    def load(cls, filepath: str):
        """Load index from file"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        index = cls(
            n_clusters=data['n_clusters'],
            prototypes_per_cluster=data['prototypes_per_cluster']
        )
        index.kmeans = data['kmeans']
        index.cluster_prototypes = data['cluster_prototypes']
        index.feature_keys = data['feature_keys']
        index.is_fitted = data['is_fitted']
        
        return index


def _predict_with_cluster_knn(
    prototypes: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    k: int = 5,
) -> Dict[str, float]:
    """KNN prediction using only prototype samples"""
    if not prototypes or not actual_map or not target_keys:
        return {}

    neighbors: List[Tuple[float, Dict[str, float]]] = []
    actual_keys = set(actual_map.keys())

    for sample in prototypes:
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
    top_neighbors = neighbors[: min(k, len(neighbors))]

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


def _predict_with_cluster_kernel_regression(
    prototypes: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    bandwidth: float = 1.0,
) -> Dict[str, float]:
    """Kernel Regression using only prototype samples"""
    if not prototypes or not actual_map or not target_keys:
        return {}

    actual_keys = set(actual_map.keys())
    
    # Calculate weights once for all target keys
    weights = []
    for sample in prototypes:
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
    
    # Predict each target key
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


def _predict_with_cluster_lwlr(
    prototypes: List[Dict[str, float]],
    actual_map: Dict[str, float],
    target_keys: Set[str],
    tau: float = 1.0,
) -> Dict[str, float]:
    """LWLR using only prototype samples"""
    if not prototypes or not actual_map or not target_keys:
        return {}

    actual_keys = set(actual_map.keys())
    predictions: Dict[str, float] = {}

    # Get common features
    common_features = actual_keys
    for sample in prototypes:
        common_features = common_features & set(sample.keys())
    
    if not common_features:
        return {}

    common_features = sorted(common_features)

    for target_key in target_keys:
        # Build training data
        X_train = []
        y_train = []

        for sample in prototypes:
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


def build_cluster_index_for_structure(
    db: Session,
    structure_id: int,
    n_clusters: Optional[int] = None,
    prototypes_per_cluster: Optional[int] = None,
    force_rebuild: bool = False
) -> Optional[ClusterPrototypeIndex]:
    """
    Build cluster+prototype index for a custom structure (with caching)
    
    Args:
        db: Database session
        structure_id: Structure ID
        n_clusters: Number of clusters (auto-calculate if None)
        prototypes_per_cluster: Max prototypes per cluster (deprecated, auto-calculated)
        force_rebuild: If True, ignore cache and rebuild
        
    Returns:
        ClusterPrototypeIndex or None if failed
    """
    # Get structure
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        return None
    
    # Load reference dataset
    samples = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).all()
    
    if not samples:
        return None
    
    dataset = [sample.score_data for sample in samples]
    dataset_size = len(dataset)
    
    # Compute dataset hash for cache validation
    dataset_for_hash = [{"id": s.id, "score_data": s.score_data} for s in samples]
    dataset_hash = compute_dataset_hash(dataset_for_hash)
    
    # Try to load from cache first (unless force_rebuild)
    if not force_rebuild:
        cached_bytes = get_cached_cluster_index(structure_id, dataset_hash)
        if cached_bytes:
            try:
                index = pickle.loads(cached_bytes)
                print(f"[CLUSTER CACHE HIT] Loaded cluster index for structure {structure_id} from cache")
                return index
            except Exception as e:
                print(f"[CLUSTER CACHE] Failed to unpickle cached index: {e}")
    
    print(f"[CLUSTER] Building new index for structure {structure_id} ({dataset_size} samples)")
    
    # Auto-calculate optimal clusters if not specified
    if n_clusters is None:
        n_clusters = calculate_optimal_clusters(dataset_size)
        print(f"[CLUSTER] Auto-calculated optimal clusters: {n_clusters} for {dataset_size} samples")
    
    # Build feature keys (all subjects x all timepoints)
    feature_keys = []
    for tp in structure.time_point_labels:
        for subject in structure.subject_labels:
            feature_keys.append(f"{subject}_{tp}")
    
    # Create and fit index
    # Note: prototypes_per_cluster is now auto-calculated per cluster in fit()
    index = ClusterPrototypeIndex(
        n_clusters=n_clusters,
        prototypes_per_cluster=50  # Max limit, actual will be calculated dynamically
    )
    
    try:
        index.fit(dataset, feature_keys)
        
        # Cache the fitted index
        try:
            pickled_index = pickle.dumps(index)
            set_cached_cluster_index(structure_id, dataset_hash, pickled_index)
            print(f"[CLUSTER] Cached cluster index for structure {structure_id} (hash: {dataset_hash[:8]}...)")
        except Exception as cache_err:
            print(f"[CLUSTER] Failed to cache index: {cache_err}")
        
        return index
    except Exception as e:
        print(f"[CLUSTER] Failed to build index: {e}")
        return None


def predict_with_cluster_index(
    index: ClusterPrototypeIndex,
    actual_map: Dict[str, float],
    target_keys: Set[str],
    model_type: str = "knn",
    model_params: Dict[str, float] = None
) -> Dict[str, float]:
    """
    Predict using cluster index
    
    Args:
        index: Fitted ClusterPrototypeIndex
        actual_map: User's current scores
        target_keys: Keys to predict
        model_type: 'knn', 'kernel_regression', or 'lwlr'
        model_params: Model parameters
        
    Returns:
        Predictions dict
    """
    if not index.is_fitted:
        return {}
    
    if model_params is None:
        model_params = {
            "knn_n": 5,
            "kr_bandwidth": 1.0,
            "lwlr_tau": 1.0
        }
    
    # Step 1: Assign to cluster
    cluster_id = index.assign_cluster(actual_map)
    
    # Step 2: Get prototypes for this cluster
    prototypes = index.get_cluster_prototypes(cluster_id)
    
    if not prototypes:
        print(f"[CLUSTER] Warning: No prototypes in cluster {cluster_id}")
        return {}
    
    print(f"[CLUSTER] Assigned to cluster {cluster_id} with {len(prototypes)} prototypes")
    
    # Step 3: Predict using local model
    if model_type == "kernel_regression":
        predictions = _predict_with_cluster_kernel_regression(
            prototypes=prototypes,
            actual_map=actual_map,
            target_keys=target_keys,
            bandwidth=model_params["kr_bandwidth"]
        )
    elif model_type == "lwlr":
        predictions = _predict_with_cluster_lwlr(
            prototypes=prototypes,
            actual_map=actual_map,
            target_keys=target_keys,
            tau=model_params["lwlr_tau"]
        )
    else:  # knn
        predictions = _predict_with_cluster_knn(
            prototypes=prototypes,
            actual_map=actual_map,
            target_keys=target_keys,
            k=model_params["knn_n"]
        )
    
    return predictions


def evaluate_cluster_models(
    db: Session,
    structure_id: int,
    input_timepoints: List[str],
    output_timepoints: List[str],
    model_params: Dict[str, float],
    n_clusters: Optional[int] = None,
    prototypes_per_cluster: Optional[int] = None  # Deprecated, auto-calculated
) -> Dict:
    """
    Evaluate models using cluster+prototype approach
    
    Faster than full dataset evaluation because:
    - Only searches within local cluster prototypes
    - Reduced computation for distance/kernel calculations
    - Auto-scales clusters and prototypes based on dataset size
    """
    print(f"[CLUSTER-EVAL] Starting cluster-based evaluation")
    
    # Try to get cached evaluation first
    cached_result = get_cached_evaluation(
        structure_id=structure_id,
        input_timepoints=input_timepoints,
        output_timepoints=output_timepoints,
        model_params=model_params,
        method="cluster"
    )
    
    if cached_result:
        print(f"[CLUSTER-EVAL] Using cached evaluation results")
        return cached_result
    
    # Get structure
    structure = db.query(models.CustomTeachingStructure).filter(
        models.CustomTeachingStructure.id == structure_id
    ).first()
    
    if not structure:
        return {"error": "Structure not found", "models": {}}
    
    # Load dataset
    samples = db.query(models.CustomDatasetSample).filter(
        models.CustomDatasetSample.structure_id == structure_id
    ).all()
    
    if len(samples) < 20:
        return {"error": "Cần ít nhất 20 mẫu", "models": {}}
    
    dataset = [sample.score_data for sample in samples]
    
    # Prepare keys
    input_keys = []
    for subject in structure.subject_labels:
        for tp in input_timepoints:
            input_keys.append(f"{subject}_{tp}")
    
    output_keys = []
    for subject in structure.subject_labels:
        for tp in output_timepoints:
            output_keys.append(f"{subject}_{tp}")
    
    # Filter valid samples
    valid_samples = []
    for sample in dataset:
        if all(key in sample and sample[key] is not None for key in input_keys + output_keys):
            valid_samples.append(sample)
    
    if len(valid_samples) < 20:
        return {"error": f"Chỉ có {len(valid_samples)} mẫu hợp lệ", "models": {}}
    
    # Build cluster index on ALL valid samples (we'll use leave-one-out style validation)
    all_feature_keys = input_keys + output_keys
    
    # Train-test split
    from sklearn.model_selection import train_test_split
    train_samples, test_samples = train_test_split(
        valid_samples, test_size=0.2, random_state=42
    )
    
    print(f"[CLUSTER-EVAL] Train: {len(train_samples)}, Test: {len(test_samples)}")
    
    # Auto-calculate optimal clusters if not specified
    if n_clusters is None:
        n_clusters = calculate_optimal_clusters(len(train_samples))
        print(f"[CLUSTER-EVAL] Auto-calculated optimal clusters: {n_clusters}")
    
    # Build index on training data
    index = ClusterPrototypeIndex(
        n_clusters=n_clusters,
        prototypes_per_cluster=50  # Max limit, actual calculated dynamically
    )
    
    try:
        index.fit(train_samples, all_feature_keys)
    except Exception as e:
        return {"error": f"Clustering failed: {e}", "models": {}}
    
    # Evaluate each model
    results = {}
    
    for model_name in ["knn", "kernel_regression", "lwlr"]:
        print(f"[CLUSTER-EVAL] Evaluating {model_name}...")
        
        predictions = []
        actuals = []
        
        for test_sample in test_samples:
            # Extract input features
            actual_map = {key: test_sample[key] for key in input_keys}
            
            # Predict output keys
            target_keys = set(output_keys)
            
            pred = predict_with_cluster_index(
                index=index,
                actual_map=actual_map,
                target_keys=target_keys,
                model_type=model_name,
                model_params=model_params
            )
            
            if pred:
                # Average predictions
                pred_avg = sum(pred.values()) / len(pred)
                predictions.append(pred_avg)
                
                # Average actuals
                actual_avg = sum(test_sample[key] for key in output_keys) / len(output_keys)
                actuals.append(actual_avg)
        
        if not predictions:
            results[model_name] = {"error": "No predictions made"}
            continue
        
        # Calculate metrics
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        mae = mean_absolute_error(actuals, predictions)
        mse = mean_squared_error(actuals, predictions)
        rmse = np.sqrt(mse)
        
        scale_max = 10.0  # Could use structure.scale_type
        accuracy = max(0, min(100, 100 - (mae / scale_max) * 100))
        
        results[model_name] = {
            "mae": round(mae, 4),
            "mse": round(mse, 4),
            "rmse": round(rmse, 4),
            "accuracy": round(accuracy, 2),
            "test_samples": len(predictions)
        }
        
        print(f"[CLUSTER-EVAL] {model_name}: MAE={mae:.4f}, Accuracy={accuracy:.2f}%")
    
    # Determine best model
    best_model = None
    best_accuracy = 0
    
    for model_name, metrics in results.items():
        if "error" not in metrics and metrics["accuracy"] > best_accuracy:
            best_accuracy = metrics["accuracy"]
            best_model = model_name
    
    model_display_names = {
        "knn": "KNN",
        "kernel_regression": "Kernel Regression",
        "lwlr": "LWLR"
    }
    
    result = {
        "models": results,
        "recommendation": model_display_names.get(best_model, "Không xác định"),
        "best_accuracy": round(best_accuracy, 2),
        "method": "cluster_prototype",
        "n_clusters": index.n_clusters,
        "total_prototypes": sum(len(p) for p in index.cluster_prototypes.values()),
        "train_samples": len(train_samples),
        "test_samples": len(test_samples)
    }
    
    # Cache the evaluation result
    set_cached_evaluation(
        structure_id=structure_id,
        input_timepoints=input_timepoints,
        output_timepoints=output_timepoints,
        model_params=model_params,
        method="cluster",
        results=result
    )
    
    return result

