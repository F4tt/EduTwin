"""
Stress Test Script for Performance Evaluation
Compares Global Scan vs Cached Query (Cluster Indexing) performance.

Sử dụng bộ dữ liệu thật từ file 10_11_12.xlsx:
- 2283 bản ghi gốc (học sinh thực tế)
- 54 cột (9 môn × 6 thời điểm: HK1+HK2 cho lớp 10, 11, 12)
- Nhân bản và thêm nhiễu để đạt các kích thước lớn hơn

Usage:
    cd backend
    python -m ml.stress_test_performance
"""

import time
import numpy as np
import pandas as pd
from typing import Dict, List, Set
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.cluster_prototype_service import (
    ClusterPrototypeIndex,
    calculate_optimal_clusters,
    predict_with_cluster_index,
    _predict_with_cluster_knn
)
from ml.custom_prediction_service import _predict_with_knn


def load_real_dataset(xlsx_path: str) -> tuple:
    """
    Load dataset từ file Excel thật (10_11_12.xlsx).
    
    Cấu trúc file:
    - 2283 dòng (học sinh)
    - 54 cột: {Môn}_{HọcKỳ}_{Lớp}
    - Môn: Toán, Văn, Lý, Hóa, Sinh, Sử, Địa, Anh, GDCD (9 môn)
    - Thời điểm: 1_10, 2_10, 1_11, 2_11, 1_12, 2_12 (6 thời điểm)
    
    Returns:
        dataset: List[Dict] - mỗi dict là điểm của 1 học sinh
        feature_keys: List[str] - tên các cột
    """
    df = pd.read_excel(xlsx_path)
    
    # Lấy danh sách cột (feature keys)
    feature_keys = list(df.columns)
    
    # Convert DataFrame thành list of dicts
    dataset = []
    for _, row in df.iterrows():
        sample = {}
        for key in feature_keys:
            value = row[key]
            if pd.notna(value):
                sample[key] = float(value)
        if sample:  # Chỉ thêm nếu có ít nhất 1 giá trị
            dataset.append(sample)
    
    return dataset, feature_keys


def replicate_dataset(original_dataset: List[Dict], target_size: int, noise_std: float = 0.3) -> List[Dict]:
    """
    Nhân bản dataset gốc để đạt kích thước mong muốn.
    Thêm nhiễu Gaussian để tạo biến thể.
    
    Args:
        original_dataset: Dataset gốc
        target_size: Kích thước mong muốn
        noise_std: Độ lệch chuẩn nhiễu (mặc định 0.3)
        
    Returns:
        Dataset được nhân bản với nhiễu
    """
    np.random.seed(42)
    
    if target_size <= len(original_dataset):
        # Nếu target nhỏ hơn, chỉ lấy một phần
        return original_dataset[:target_size]
    
    result = []
    original_len = len(original_dataset)
    
    for i in range(target_size):
        # Lấy sample gốc (lặp vòng)
        original = original_dataset[i % original_len]
        
        if i < original_len:
            # Giữ nguyên dataset gốc
            result.append(original.copy())
        else:
            # Tạo bản sao với nhiễu
            noisy = {}
            for key, value in original.items():
                # Thêm nhiễu Gaussian, giới hạn trong [0, 10]
                noise = np.random.normal(0, noise_std)
                noisy_value = max(0, min(10, value + noise))
                noisy[key] = round(noisy_value, 2)
            result.append(noisy)
    
    return result


def suppress_stdout():
    """Context manager to suppress stdout"""
    class DevNull:
        def write(self, msg): pass
        def flush(self): pass
    return DevNull()


def benchmark_global_scan(dataset: List[Dict], query: Dict, target_keys: Set[str], k: int = 5, runs: int = 5) -> float:
    """Benchmark Global Scan (full dataset prediction)"""
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        _predict_with_knn(dataset, query, target_keys, k)
        end = time.perf_counter()
        times.append((end - start) * 1000)
    return np.median(times)


def benchmark_cached_query(index: ClusterPrototypeIndex, query: Dict, target_keys: Set[str], runs: int = 5) -> float:
    """Benchmark Cached Query (cluster-based prediction)"""
    model_params = {"knn_n": 5, "kr_bandwidth": 1.0, "lwlr_tau": 1.0}
    times = []
    for _ in range(runs):
        old_stdout = sys.stdout
        sys.stdout = suppress_stdout()
        try:
            start = time.perf_counter()
            predict_with_cluster_index(index, query, target_keys, "knn", model_params)
            end = time.perf_counter()
        finally:
            sys.stdout = old_stdout
        times.append((end - start) * 1000)
    return np.median(times)


def run_stress_test():
    """Run stress test comparing Global Scan vs Cached Query"""
    
    lines = []
    def log(msg=""):
        lines.append(msg)
        print(msg)
    
    log("=" * 80)
    log("STRESS TEST: Global Scan vs Cached Query (Cluster Indexing)")
    log("=" * 80)
    log()
    log("Nguồn dữ liệu: 10_11_12.xlsx (2283 học sinh thực tế)")
    log("Cấu trúc: 9 môn × 6 thời điểm = 54 features")
    log("Phương pháp: Nhân bản + thêm nhiễu N(0, 0.3) để đạt kích thước test")
    log()
    
    # Load real dataset
    xlsx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "10_11_12.xlsx")
    log(f"Loading dataset from: {xlsx_path}")
    
    try:
        original_dataset, feature_keys = load_real_dataset(xlsx_path)
        log(f"Loaded {len(original_dataset)} original samples, {len(feature_keys)} features")
    except Exception as e:
        log(f"ERROR: Cannot load dataset: {e}")
        return
    
    # Test sizes
    test_sizes = [1_000, 10_000, 50_000, 100_000]
    results = []
    
    for n_samples in test_sizes:
        log(f"\n{'='*60}")
        log(f"Dataset Size: {n_samples:,}")
        log(f"{'='*60}")
        
        log("Replicating dataset with noise...")
        dataset = replicate_dataset(original_dataset, n_samples)
        
        # Prepare query (use first sample as input)
        query = dataset[0].copy()
        # Use timepoints 10, 11 as input, predict 12
        input_keys = [k for k in feature_keys if '_10' in k or '_11' in k]
        target_keys = set([k for k in feature_keys if '_12' in k])
        query_input = {k: query[k] for k in input_keys if k in query}
        
        n_clusters = calculate_optimal_clusters(n_samples)
        log(f"Clusters: {n_clusters}")
        
        log("Building cluster index...")
        
        # Suppress output during fit
        old_stdout = sys.stdout
        sys.stdout = suppress_stdout()
        try:
            index = ClusterPrototypeIndex(n_clusters=n_clusters, random_state=42)
            index.fit(dataset, feature_keys)
        finally:
            sys.stdout = old_stdout
        
        total_in_clusters = sum(len(p) for p in index.cluster_prototypes.values())
        avg_per_cluster = total_in_clusters // max(1, n_clusters)
        log(f"Samples stored: {total_in_clusters}, Avg per cluster: {avg_per_cluster}")
        
        log("Benchmarking Global Scan...")
        global_scan_time = benchmark_global_scan(dataset, query_input, target_keys)
        log(f"  Global Scan: {global_scan_time:.2f} ms")
        
        log("Benchmarking Cached Query...")
        cached_query_time = benchmark_cached_query(index, query_input, target_keys)
        log(f"  Cached Query: {cached_query_time:.2f} ms")
        
        speedup = global_scan_time / cached_query_time if cached_query_time > 0 else 0
        log(f"  Speedup: {speedup:.2f}x")
        
        results.append({
            'n': n_samples,
            'clusters': n_clusters,
            'avg_per_cluster': avg_per_cluster,
            'global_scan_ms': global_scan_time,
            'cached_query_ms': cached_query_time,
            'speedup': speedup
        })
    
    log()
    log()
    log("=" * 80)
    log("SUMMARY RESULTS")
    log("=" * 80)
    log()
    log(f"{'N':>12}  {'Clusters':>10}  {'Avg/Cluster':>12}  {'Global(ms)':>12}  {'Cached(ms)':>12}  {'Speedup':>10}")
    log("-" * 75)
    
    for r in results:
        log(f"{r['n']:>12,}  {r['clusters']:>10}  {r['avg_per_cluster']:>12}  {r['global_scan_ms']:>12.2f}  {r['cached_query_ms']:>12.2f}  {r['speedup']:>9.2f}x")
    
    log()
    log("=" * 80)
    log("TEST COMPLETE")
    log("=" * 80)
    
    # Save to file
    with open("stress_test_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log("\n[Saved to stress_test_report.txt]")


if __name__ == "__main__":
    run_stress_test()
