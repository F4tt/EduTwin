"""
Educational Knowledge Base for LLM Context
Provides domain-specific knowledge about Vietnamese education system and scoring standards.
"""

EDUCATIONAL_KNOWLEDGE = """
# KIẾN THỨC NỀN VỀ HỆ THỐNG GIÁO DỤC VIỆT NAM

## 1. THANG ĐIỂM VÀ PHÂN LOẠI HỌC LỰC

### Thang điểm: 0-10
- 0-2: Kém, cần cải thiện nghiêm túc
- 2-3.5: Yếu, cần nỗ lực nhiều hơn
- 3.5-5: Trung bình yếu, cần tập trung học tập
- 5-6.5: Trung bình, đạt yêu cầu cơ bản
- 6.5-8: Khá, thành tích tốt
- 8-9: Giỏi, xuất sắc
- 9-10: Xuất sắc, rất ưu tú

### Điểm trung bình (GPA):
- < 5.0: Yếu - Cần cải thiện toàn diện
- 5.0-6.4: Trung bình - Đạt chuẩn
- 6.5-7.9: Khá - Tốt
- 8.0-8.9: Giỏi - Rất tốt
- 9.0-10: Xuất sắc - Ưu tú

## 2. CÁC MỐC QUAN TRỌNG

### Điểm chuẩn đại học (tham khảo):
- Ngành Y: 27-29/30 (trung bình 9.0-9.7/môn)
- Ngành kỹ thuật hàng đầu: 24-27/30 (trung bình 8.0-9.0/môn)
- Các trường top: 20-24/30 (trung bình 6.7-8.0/môn)
- Đại học công lập phổ thông: 15-20/30 (trung bình 5.0-6.7/môn)

### Mục tiêu thực tế theo năng lực:
- Học sinh yếu (< 5): Mục tiêu đạt 5.0-6.0 (tăng 1-2 điểm)
- Học sinh trung bình (5-6.5): Mục tiêu đạt 7.0-7.5 (tăng 1-1.5 điểm)
- Học sinh khá (6.5-8): Mục tiêu đạt 8.5-9.0 (tăng 0.5-1 điểm)
- Học sinh giỏi (8-9): Mục tiêu duy trì hoặc đạt 9.5+ (tăng 0.5 điểm)

## 3. XU HƯỚNG VÀ PHÂN TÍCH

### Đánh giá xu hướng:
- Tăng 0.5+ điểm: Tiến bộ tốt, duy trì phương pháp
- Tăng 0.2-0.5: Tiến bộ ổn định
- Không đổi (±0.2): Ổn định, cần động lực mới
- Giảm 0.2-0.5: Cảnh báo, cần xem xét lại
- Giảm > 0.5: Cần can thiệp khẩn cấp

### Phân tích điểm môn:
- Chênh lệch > 2 điểm giữa các môn: Mất cân bằng, cần điều chỉnh
- Điểm lý thuyết cao, thực hành thấp: Thiếu vận dụng
- Điểm dao động mạnh: Thiếu ổn định, cần củng cố nền tảng

## 4. KHỐI THI VÀ TỔ HỢP MÔN

### Khối thi chính:
- **A00**: Toán, Lý, Hóa - Khối tự nhiên cơ bản
- **A01**: Toán, Lý, Anh - Kỹ thuật quốc tế
- **B00**: Toán, Hóa, Sinh - Y dược, sinh học
- **C00**: Văn, Sử, Địa - Khoa học xã hội
- **D01**: Toán, Văn, Anh - Kinh tế, ngôn ngữ
- **D07**: Toán, Hóa, Anh - Công nghệ thực phẩm
- **D14**: Toán, Văn, GDCD - Luật

### Đánh giá theo khối:
- Khối A: Cần tư duy logic, kỹ năng tính toán
- Khối B: Cần khả năng ghi nhớ, phân tích
- Khối C: Cần tư duy phản biện, văn phong
- Khối D: Cần cân bằng giữa lý thuyết và ứng dụng

## 5. LỜI KHUYÊN THEO BỐI CẢNH

### Khi điểm thấp:
- Tập trung vào nền tảng, không vội vàng
- Ưu tiên 2-3 môn yếu nhất
- Tạo thói quen học đều đặn
- Tìm người hướng dẫn hoặc nhóm học

### Khi điểm trung bình:
- Phát triển thế mạnh, củng cố điểm yếu
- Tăng cường luyện đề, bài tập nâng cao
- Xác định rõ mục tiêu đại học

### Khi điểm cao:
- Duy trì ổn định, tránh chủ quan
- Học sâu, mở rộng kiến thức
- Hướng tới các kỳ thi học sinh giỏi
- Cân bằng học tập và phát triển kỹ năng mềm

## 6. SO SÁNH VỚI MẶT BẰNG CHUNG

### Phân vị điểm (percentile):
- Top 10%: GPA ≥ 8.5
- Top 25%: GPA ≥ 7.5
- Top 50%: GPA ≥ 6.5
- Top 75%: GPA ≥ 5.5

### Đánh giá vị trí:
- Trên trung bình: GPA > 6.5
- Trung bình: GPA 5.0-6.5
- Dưới trung bình: GPA < 5.0

## 7. DẤU HIỆU CẦN LƯU Ý

### Dấu hiệu tích cực:
- Xu hướng tăng đều qua các học kỳ
- Điểm cân bằng giữa các môn
- Điểm thực tế gần với dự đoán (cho thấy ổn định)

### Dấu hiệu cần cải thiện:
- Xu hướng giảm liên tục
- Chênh lệch lớn giữa các môn
- Điểm thực tế thấp hơn nhiều so với dự đoán
- Điểm dao động mạnh (thiếu ổn định)

## 8. NGUYÊN TẮC TƯ VẤN

1. **Thực tế**: Dựa trên dữ liệu cụ thể, không chung chung
2. **Khích lệ**: Luôn tìm điểm tích cực, động viên
3. **Cụ thể**: Đưa ra hành động rõ ràng, có thể làm được
4. **Cân bằng**: Vừa chỉ ra vấn đề, vừa đưa giải pháp
5. **Tôn trọng**: Hiểu rằng mỗi học sinh có hoàn cảnh riêng
"""

def get_educational_context() -> str:
    """Returns the educational knowledge base for LLM context."""
    return EDUCATIONAL_KNOWLEDGE


def get_score_classification(score: float) -> dict:
    """Classify a score and return detailed information."""
    if score < 0 or score > 10:
        return {"level": "Invalid", "description": "Điểm không hợp lệ"}
    
    if score < 2:
        return {
            "level": "Kém",
            "description": "Cần cải thiện nghiêm túc",
            "advice": "Tập trung vào kiến thức cơ bản, tìm sự hỗ trợ từ giáo viên"
        }
    elif score < 3.5:
        return {
            "level": "Yếu",
            "description": "Cần nỗ lực nhiều hơn",
            "advice": "Ôn luyện đều đặn, làm bài tập cơ bản mỗi ngày"
        }
    elif score < 5:
        return {
            "level": "Trung bình yếu",
            "description": "Cần tập trung học tập",
            "advice": "Củng cố kiến thức nền, tăng thời gian tự học"
        }
    elif score < 6.5:
        return {
            "level": "Trung bình",
            "description": "Đạt yêu cầu cơ bản",
            "advice": "Phát triển thêm để đạt khá, luyện tập thường xuyên"
        }
    elif score < 8:
        return {
            "level": "Khá",
            "description": "Thành tích tốt",
            "advice": "Duy trì và nâng cao, học sâu hơn các phần khó"
        }
    elif score < 9:
        return {
            "level": "Giỏi",
            "description": "Xuất sắc",
            "advice": "Tiếp tục phát huy, tham gia các kỳ thi nâng cao"
        }
    else:
        return {
            "level": "Xuất sắc",
            "description": "Rất ưu tú",
            "advice": "Duy trì thành tích, mở rộng kiến thức chuyên sâu"
        }


def get_gpa_classification(gpa: float) -> dict:
    """Classify GPA and return detailed information."""
    if gpa < 5.0:
        return {
            "level": "Yếu",
            "description": "Cần cải thiện toàn diện",
            "percentile": "Dưới trung bình",
            "target": "Mục tiêu: đạt 5.0-6.0"
        }
    elif gpa < 6.5:
        return {
            "level": "Trung bình",
            "description": "Đạt chuẩn",
            "percentile": "Trung bình (50-75%)",
            "target": "Mục tiêu: đạt 7.0-7.5"
        }
    elif gpa < 8.0:
        return {
            "level": "Khá",
            "description": "Tốt",
            "percentile": "Khá (25-50%)",
            "target": "Mục tiêu: đạt 8.0-8.5"
        }
    elif gpa < 9.0:
        return {
            "level": "Giỏi",
            "description": "Rất tốt",
            "percentile": "Top 10-25%",
            "target": "Mục tiêu: duy trì hoặc đạt 9.0+"
        }
    else:
        return {
            "level": "Xuất sắc",
            "description": "Ưu tú",
            "percentile": "Top 10%",
            "target": "Mục tiêu: duy trì 9.0+ và phát triển chuyên sâu"
        }


def analyze_score_trend(scores: list) -> dict:
    """
    Analyze trend from a list of scores (chronological order).
    Returns trend type and description.
    """
    if len(scores) < 2:
        return {"trend": "insufficient_data", "description": "Chưa đủ dữ liệu để phân tích xu hướng"}
    
    # Calculate average change
    changes = [scores[i] - scores[i-1] for i in range(1, len(scores))]
    avg_change = sum(changes) / len(changes)
    
    if avg_change >= 0.5:
        return {
            "trend": "strong_improvement",
            "description": "Tiến bộ rõ rệt",
            "advice": "Tuyệt vời! Hãy duy trì phương pháp học hiện tại"
        }
    elif avg_change >= 0.2:
        return {
            "trend": "improvement",
            "description": "Tiến bộ ổn định",
            "advice": "Đang đi đúng hướng, tiếp tục phát huy"
        }
    elif avg_change >= -0.2:
        return {
            "trend": "stable",
            "description": "Ổn định",
            "advice": "Cần thay đổi phương pháp học để có bước tiến mới"
        }
    elif avg_change >= -0.5:
        return {
            "trend": "declining",
            "description": "Có xu hướng giảm",
            "advice": "Cần xem xét lại phương pháp học và quản lý thời gian"
        }
    else:
        return {
            "trend": "strong_decline",
            "description": "Giảm đáng kể",
            "advice": "Cần can thiệp ngay: tìm hiểu nguyên nhân và điều chỉnh"
        }


def compare_with_benchmark(user_scores: dict, dataset_scores: list) -> dict:
    """
    Compare user scores with dataset benchmark.
    
    Args:
        user_scores: dict with subject as key, score as value
        dataset_scores: list of score dictionaries from reference dataset
    
    Returns:
        Comparison analysis
    """
    if not user_scores or not dataset_scores:
        return {"status": "insufficient_data"}
    
    user_avg = sum(user_scores.values()) / len(user_scores)
    
    # Calculate percentiles from dataset
    all_averages = []
    for record in dataset_scores:
        scores = [v for v in record.values() if isinstance(v, (int, float)) and 0 <= v <= 10]
        if scores:
            all_averages.append(sum(scores) / len(scores))
    
    if not all_averages:
        return {"status": "no_benchmark_data"}
    
    all_averages.sort()
    percentile = sum(1 for avg in all_averages if avg < user_avg) / len(all_averages) * 100
    
    median = all_averages[len(all_averages) // 2]
    top_10_threshold = all_averages[int(len(all_averages) * 0.9)]
    top_25_threshold = all_averages[int(len(all_averages) * 0.75)]
    
    return {
        "user_average": round(user_avg, 2),
        "percentile": round(percentile, 1),
        "median": round(median, 2),
        "top_10_threshold": round(top_10_threshold, 2),
        "top_25_threshold": round(top_25_threshold, 2),
        "position": "Trên trung bình" if user_avg > median else "Trung bình" if user_avg >= median * 0.9 else "Dưới trung bình",
        "distance_to_top_10": round(top_10_threshold - user_avg, 2),
        "distance_to_top_25": round(top_25_threshold - user_avg, 2)
    }
