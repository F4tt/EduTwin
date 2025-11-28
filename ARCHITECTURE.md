# Kiến trúc phân quyền và quản lý dữ liệu EduTwin

## Tổng quan
EduTwin sử dụng mô hình phân quyền 2 cấp:
- **Admin/Developer**: Quản lý dataset tham chiếu, mô hình ML, tham số → áp dụng cho **TOÀN HỆ THỐNG**
- **User thường**: Quản lý dữ liệu học tập cá nhân (điểm số, tài liệu), sử dụng dataset/model do admin cung cấp

## Dữ liệu được phân tách theo User (User-Specific Data)

### 1. Điểm số học tập - `StudyScore`
- Mỗi user có bảng điểm riêng
- Filter: `user_id`
- CRUD: Chỉ user đó được thao tác

### 2. Tài liệu học tập - `LearningDocument`  
- Mỗi user có tài liệu riêng (từ điểm số, chatbot)
- Filter: `user_id`
- Vector embeddings cũng được phân tách theo user

### 3. Chat Sessions & Messages
- Mỗi user có lịch sử chat riêng
- Filter: `user_id`

### 4. Learning Goals
- Mục tiêu học tập cá nhân
- Filter: `user_id`

### 5. Pending Updates
- Tracking thay đổi dữ liệu của user
- Filter: `user_id`

## Dữ liệu dùng chung toàn hệ thống (System-Wide Data)

### 1. Dataset tham chiếu - `KNNReferenceSample`
- **Quản lý bởi**: Admin/Developer
- **Import**: Admin import Excel → áp dụng cho **TẤT CẢ users**
- **Khi import mới**: Xóa toàn bộ dataset cũ, thay thế bằng dataset mới
- **Mục đích**: Làm cơ sở để dự đoán điểm cho tất cả học sinh
- **Lưu ý**: Cột `user_id` tồn tại nhưng **KHÔNG được sử dụng** (nullable)

### 2. Model Configuration - `MLModelConfig`
- Chọn model active: KNN, Kernel Regression, hoặc LWLR
- **Admin/Developer** thay đổi → **TẤT CẢ users** sử dụng model mới

### 3. Model Parameters - `ModelParameters`
- Tham số cho từng model: `knn_n`, `kr_bandwidth`, `lwlr_tau`
- **Admin/Developer** điều chỉnh → **TẤT CẢ users** dùng tham số mới

## Workflow điển hình

### Admin/Developer workflow:
1. Login với role `admin` hoặc `developer`
2. Truy cập Developer Tools (`/developer`)
3. **Import Dataset**: Upload file Excel → Thay thế toàn bộ dataset cũ
4. **Đánh giá Model**: Chạy evaluation trên dataset mới
5. **Chọn Model**: Thay đổi `active_model` (KNN/Kernel/LWLR)
6. **Điều chỉnh tham số**: Cập nhật `knn_n`, `kr_bandwidth`, `lwlr_tau`
7. → **Tất cả users** tự động sử dụng dataset/model/tham số mới

### User thường workflow:
1. Login với role `user` (default)
2. **Nhập điểm số**: Tạo/cập nhật `StudyScore` của riêng mình
3. **ML Pipeline tự động chạy**: Dự đoán điểm dựa trên:
   - Điểm thực tế của user (user-specific)
   - Dataset tham chiếu (system-wide, do admin cung cấp)
   - Model và tham số (system-wide, do admin chọn)
4. **Xem phân tích AI**: So sánh với dataset tham chiếu chung
5. **Chat với AI**: Dựa trên tài liệu học tập riêng + knowledge base chung

## Phân quyền

### 🔒 Chỉ admin/developer được:
- Import dataset tham chiếu
- Thay đổi ML model
- Điều chỉnh tham số model
- Xem dataset status
- Chạy model evaluation
- Truy cập Developer Tools

### ✅ User thường được:
- Quản lý điểm số của mình
- Chat với AI tutor
- Xem phân tích (dựa trên dataset chung)
- Đặt mục tiêu học tập
- Cập nhật profile cá nhân

## Bảo mật dữ liệu

### ✅ Dữ liệu riêng tư (được bảo vệ):
- Điểm số học tập (StudyScore) - chỉ user đó thấy
- Lịch sử chat (ChatSession, ChatMessage) - chỉ user đó thấy
- Tài liệu học tập (LearningDocument) - chỉ user đó thấy
- Mục tiêu học tập (LearningGoal) - chỉ user đó thấy

### ⚠️ Dữ liệu dùng chung (system-wide):
- Dataset tham chiếu (KNNReferenceSample) - quản lý bởi admin
- Model config (MLModelConfig) - quản lý bởi admin
- Model parameters (ModelParameters) - quản lý bởi admin

## Frontend: AI Insights Cache

Để tránh user này thấy AI insights của user khác:

### LocalStorage Key Strategy
```javascript
// OLD (bug): 'dataviz_ai_comments' - chung cho tất cả users
// NEW (fixed): 'dataviz_ai_comments_{username}' - riêng cho từng user
const storageKey = `dataviz_ai_comments_${user.username}`;
```

### Cache Management
- **Login**: Load cache của user hiện tại
- **Logout**: Xóa cache của user đó
- **Switch user**: Tự động load cache của user mới

## Testing Checklist

✅ **Dataset & Model (System-wide)**:
1. Admin import dataset → Tất cả users thấy predictions mới
2. Admin thay đổi model → Tất cả users dùng model mới
3. Admin điều chỉnh tham số → Tất cả users dùng tham số mới

✅ **User Data (User-specific)**:
4. User A nhập điểm → Chỉ User A thấy
5. User B nhập điểm → Không ảnh hưởng User A
6. Predictions của mỗi user = điểm riêng + dataset chung

✅ **Security**:
7. User thường không thể import dataset
8. User thường không thể thay đổi model/tham số
9. User không thấy điểm/chat của user khác

✅ **Frontend Cache**:
10. User A logout → cache A bị xóa
11. User B login → thấy cache B (không thấy cache A)
12. AI insights riêng biệt cho từng user

## Files đã thay đổi

### Backend:
- `backend/db/models.py` - Schema với user_id (nullable)
- `backend/main.py` - Migration SQL
- `backend/services/excel_importer.py` - Import dataset chung
- `backend/ml/prediction_service.py` - Load dataset chung
- `backend/services/dataset_analyzer.py` - Analyze dataset chung
- `backend/services/model_evaluator.py` - Evaluate dataset chung
- `backend/api/developer.py` - API quản lý system-wide data

### Frontend:
- `frontend_react/src/pages/DataViz.jsx` - Cache theo username
- `frontend_react/src/context/AuthContext.jsx` - Clear cache on logout
- `frontend_react/src/components/Layout.jsx` - Display "Họ Tên"
