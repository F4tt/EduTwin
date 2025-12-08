"""
ML Prediction Cache Service
Caches prediction results and model evaluations to improve performance
"""

import hashlib
import json
from typing import Dict, Optional, Any
import os

# Import redis_client from session_utils
try:
    from utils.session_utils import redis_client
    REDIS_AVAILABLE = True
except Exception as e:
    print(f"[CACHE] Redis not available: {e}")
    REDIS_AVAILABLE = False
    redis_client = None

# Cache TTL (time-to-live) in seconds
PREDICTION_CACHE_TTL = int(os.getenv("PREDICTION_CACHE_TTL", 3600))  # 1 hour
EVALUATION_CACHE_TTL = int(os.getenv("EVALUATION_CACHE_TTL", 7200))  # 2 hours
CLUSTER_CACHE_TTL = int(os.getenv("CLUSTER_CACHE_TTL", 86400))  # 24 hours - clusters rarely change


def _create_hash(data: Any) -> str:
    """Create MD5 hash from data"""
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()


def get_prediction_cache_key(
    user_id: int,
    structure_id: int,
    current_time_point: str,
    actual_scores: Dict[str, float],
    model_type: str,
    model_params: Dict[str, float]
) -> str:
    """
    Generate cache key for prediction results
    
    Key format: prediction:{user_id}:{structure_id}:{tp}:{hash}
    """
    # Create hash from scores + model + params
    cache_data = {
        "scores": actual_scores,
        "model": model_type,
        "params": model_params
    }
    data_hash = _create_hash(cache_data)
    
    return f"prediction:{user_id}:{structure_id}:{current_time_point}:{data_hash}"


def get_evaluation_cache_key(
    structure_id: int,
    input_timepoints: list,
    output_timepoints: list,
    model_params: Dict[str, float],
    method: str = "standard"
) -> str:
    """
    Generate cache key for model evaluation results
    
    Key format: evaluation:{structure_id}:{method}:{hash}
    """
    cache_data = {
        "input_tp": sorted(input_timepoints),
        "output_tp": sorted(output_timepoints),
        "params": model_params,
        "method": method
    }
    data_hash = _create_hash(cache_data)
    
    return f"evaluation:{structure_id}:{method}:{data_hash}"


def get_cached_prediction(
    user_id: int,
    structure_id: int,
    current_time_point: str,
    actual_scores: Dict[str, float],
    model_type: str,
    model_params: Dict[str, float]
) -> Optional[Dict[str, float]]:
    """
    Try to get cached prediction results
    
    Returns:
        Dict of predictions if cache hit, None if cache miss
    """
    if not REDIS_AVAILABLE:
        return None
    
    try:
        cache_key = get_prediction_cache_key(
            user_id, structure_id, current_time_point,
            actual_scores, model_type, model_params
        )
        
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            print(f"[CACHE HIT] Loaded predictions from cache: {cache_key}")
            return json.loads(cached_data)
        else:
            print(f"[CACHE MISS] No cached predictions found")
            return None
            
    except Exception as e:
        print(f"[CACHE ERROR] Failed to get cached prediction: {e}")
        return None


def set_cached_prediction(
    user_id: int,
    structure_id: int,
    current_time_point: str,
    actual_scores: Dict[str, float],
    model_type: str,
    model_params: Dict[str, float],
    predictions: Dict[str, float]
) -> bool:
    """
    Cache prediction results
    
    Returns:
        True if cached successfully, False otherwise
    """
    if not REDIS_AVAILABLE:
        return False
    
    try:
        cache_key = get_prediction_cache_key(
            user_id, structure_id, current_time_point,
            actual_scores, model_type, model_params
        )
        
        redis_client.setex(
            cache_key,
            PREDICTION_CACHE_TTL,
            json.dumps(predictions)
        )
        
        print(f"[CACHE SET] Cached predictions for {PREDICTION_CACHE_TTL}s: {cache_key}")
        return True
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to cache prediction: {e}")
        return False


def get_cached_evaluation(
    structure_id: int,
    input_timepoints: list,
    output_timepoints: list,
    model_params: Dict[str, float],
    method: str = "standard"
) -> Optional[Dict]:
    """
    Try to get cached evaluation results
    
    Returns:
        Dict of evaluation results if cache hit, None if cache miss
    """
    if not REDIS_AVAILABLE:
        return None
    
    try:
        cache_key = get_evaluation_cache_key(
            structure_id, input_timepoints, output_timepoints,
            model_params, method
        )
        
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            print(f"[CACHE HIT] Loaded evaluation from cache: {cache_key}")
            return json.loads(cached_data)
        else:
            print(f"[CACHE MISS] No cached evaluation found")
            return None
            
    except Exception as e:
        print(f"[CACHE ERROR] Failed to get cached evaluation: {e}")
        return None


def set_cached_evaluation(
    structure_id: int,
    input_timepoints: list,
    output_timepoints: list,
    model_params: Dict[str, float],
    method: str,
    results: Dict
) -> bool:
    """
    Cache evaluation results
    
    Returns:
        True if cached successfully, False otherwise
    """
    if not REDIS_AVAILABLE:
        return False
    
    try:
        cache_key = get_evaluation_cache_key(
            structure_id, input_timepoints, output_timepoints,
            model_params, method
        )
        
        redis_client.setex(
            cache_key,
            EVALUATION_CACHE_TTL,
            json.dumps(results)
        )
        
        print(f"[CACHE SET] Cached evaluation for {EVALUATION_CACHE_TTL}s: {cache_key}")
        return True
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to cache evaluation: {e}")
        return False


def invalidate_prediction_cache(
    user_id: Optional[int] = None,
    structure_id: Optional[int] = None
) -> int:
    """
    Invalidate prediction cache
    
    Args:
        user_id: If provided, only invalidate for this user
        structure_id: If provided, only invalidate for this structure
        
    Returns:
        Number of keys deleted
    """
    if not REDIS_AVAILABLE:
        return 0
    
    try:
        if user_id and structure_id:
            pattern = f"prediction:{user_id}:{structure_id}:*"
        elif structure_id:
            pattern = f"prediction:*:{structure_id}:*"
        elif user_id:
            pattern = f"prediction:{user_id}:*"
        else:
            pattern = "prediction:*"
        
        deleted = 0
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
            deleted += 1
        
        print(f"[CACHE INVALIDATE] Deleted {deleted} prediction cache keys")
        return deleted
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to invalidate prediction cache: {e}")
        return 0


def invalidate_evaluation_cache(structure_id: Optional[int] = None) -> int:
    """
    Invalidate evaluation cache
    
    Args:
        structure_id: If provided, only invalidate for this structure
        
    Returns:
        Number of keys deleted
    """
    if not REDIS_AVAILABLE:
        return 0
    
    try:
        if structure_id:
            pattern = f"evaluation:{structure_id}:*"
        else:
            pattern = "evaluation:*"
        
        deleted = 0
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
            deleted += 1
        
        print(f"[CACHE INVALIDATE] Deleted {deleted} evaluation cache keys")
        return deleted
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to invalidate evaluation cache: {e}")
        return 0


def get_cache_stats() -> Dict:
    """Get cache statistics"""
    if not REDIS_AVAILABLE:
        return {"status": "disabled"}
    
    try:
        # Count keys by pattern
        prediction_keys = sum(1 for _ in redis_client.scan_iter(match="prediction:*"))
        evaluation_keys = sum(1 for _ in redis_client.scan_iter(match="evaluation:*"))
        cluster_keys = sum(1 for _ in redis_client.scan_iter(match="cluster:*"))
        
        # Get Redis info
        info = redis_client.info()
        
        return {
            "status": "enabled",
            "prediction_cached": prediction_keys,
            "evaluation_cached": evaluation_keys,
            "cluster_cached": cluster_keys,
            "total_keys": info.get("db0", {}).get("keys", 0),
            "memory_used": info.get("used_memory_human", "N/A"),
            "ttl": {
                "prediction": PREDICTION_CACHE_TTL,
                "evaluation": EVALUATION_CACHE_TTL,
                "cluster": CLUSTER_CACHE_TTL
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================
# CLUSTER + PROTOTYPE CACHING
# ============================================

def get_cluster_cache_key(structure_id: int, dataset_hash: str) -> str:
    """
    Generate cache key for cluster + prototype data
    
    Key format: cluster:{structure_id}:{dataset_hash}
    """
    return f"cluster:{structure_id}:{dataset_hash}"


def compute_dataset_hash(dataset_samples: list) -> str:
    """
    Compute hash of dataset for cache invalidation
    
    Args:
        dataset_samples: List of sample dicts from database
        
    Returns:
        MD5 hash string
    """
    # Sort by sample ID to ensure consistent hashing
    sorted_data = sorted(
        [{"id": s.get("id"), "data": s.get("score_data", {})} for s in dataset_samples],
        key=lambda x: x.get("id", 0)
    )
    return _create_hash(sorted_data)


def get_cached_cluster_index(
    structure_id: int,
    dataset_hash: str
) -> Optional[bytes]:
    """
    Try to get cached cluster index (pickled ClusterPrototypeIndex)
    
    Returns:
        Pickled bytes if cache hit, None if cache miss
    """
    if not REDIS_AVAILABLE:
        return None
    
    try:
        cache_key = get_cluster_cache_key(structure_id, dataset_hash)
        cached_data = redis_client.get(cache_key)
        
        if cached_data:
            print(f"[CACHE HIT] Loaded cluster index from cache for structure {structure_id}")
            return cached_data
        else:
            print(f"[CACHE MISS] No cached cluster index for structure {structure_id}")
            return None
            
    except Exception as e:
        print(f"[CACHE ERROR] Failed to get cached cluster index: {e}")
        return None


def set_cached_cluster_index(
    structure_id: int,
    dataset_hash: str,
    pickled_index: bytes
) -> bool:
    """
    Cache cluster index (pickled ClusterPrototypeIndex)
    
    Args:
        structure_id: Structure ID
        dataset_hash: Hash of dataset for invalidation
        pickled_index: Pickled ClusterPrototypeIndex bytes
        
    Returns:
        True if cached successfully, False otherwise
    """
    if not REDIS_AVAILABLE:
        return False
    
    try:
        cache_key = get_cluster_cache_key(structure_id, dataset_hash)
        
        redis_client.setex(
            cache_key,
            CLUSTER_CACHE_TTL,
            pickled_index
        )
        
        print(f"[CACHE SET] Cached cluster index for structure {structure_id} (TTL: {CLUSTER_CACHE_TTL}s)")
        return True
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to cache cluster index: {e}")
        return False


def invalidate_cluster_cache(structure_id: Optional[int] = None) -> int:
    """
    Invalidate cluster cache
    
    Args:
        structure_id: If provided, only invalidate for this structure
        
    Returns:
        Number of keys deleted
    """
    if not REDIS_AVAILABLE:
        return 0
    
    try:
        if structure_id:
            pattern = f"cluster:{structure_id}:*"
        else:
            pattern = "cluster:*"
        
        deleted = 0
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
            deleted += 1
        
        if deleted > 0:
            print(f"[CACHE INVALIDATE] Deleted {deleted} cluster cache keys for structure {structure_id or 'ALL'}")
        return deleted
        
    except Exception as e:
        print(f"[CACHE ERROR] Failed to invalidate cluster cache: {e}")
        return 0

