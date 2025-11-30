# HỆ THỐNG EDUTWIN - TÀI LIỆU CHI TIẾT

## 📋 THÔNG TIN DỰ ÁN

**Tên dự án:** EduTwin - Hệ thống Hỗ trợ Học tập Thông minh  
**Phiên bản:** 1.0.0  
**Ngày hoàn thành:** November 2025  
**Repository:** https://github.com/F4tt/EduTwin  

---

## 🎯 TỔNG QUAN HỆ THỐNG

### 1.1. Giới thiệu

EduTwin là một hệ thống web application thông minh được thiết kế để hỗ trợ học sinh trung học phổ thông (THPT) trong việc theo dõi, dự đoán và cải thiện kết quả học tập. Hệ thống kết hợp công nghệ Machine Learning, Natural Language Processing và Chatbot AI để cung cấp trải nghiệm học tập cá nhân hóa.

### 1.2. Mục tiêu

- **Dự đoán điểm số:** Sử dụng 3 thuật toán ML (KNN, Kernel Regression, LWLR) để dự đoán điểm số các môn học
- **Chatbot thông minh:** Tích hợp Gemini API để tư vấn học tập và cập nhật thông tin
- **Theo dõi tiến độ:** Visualize kết quả học tập qua các biểu đồ và dashboard
- **Cá nhân hóa:** Học tập từ thói quen và sở thích của người dùng
- **Phân tích dữ liệu:** Cung cấp insights về dataset và benchmark so sánh

### 1.3. Đối tượng sử dụng

- **Học sinh THPT:** Lớp 10, 11, 12 - theo dõi và dự đoán kết quả học tập
- **Giáo viên/Phụ huynh:** Theo dõi tiến độ học sinh
- **Developer/Admin:** Quản lý dataset, cấu hình mô hình ML, đánh giá hiệu suất

---

## 🏗️ KIẾN TRÚC HỆ THỐNG

### 2.1. Sơ đồ Kiến trúc Tổng quan

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  React Frontend (Vite)                                │   │
│  │  - Single Page Application                            │   │
│  │  - Real-time updates via WebSocket                    │   │
│  │  - Responsive UI with Chart.js & Recharts             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend                                      │   │
│  │  ├── REST API Endpoints                               │   │
│  │  ├── WebSocket Manager (Socket.IO)                    │   │
│  │  ├── Authentication & Authorization                   │   │
│  │  └── Business Logic Services                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                            │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │  ML Service    │  │ Chatbot Service│  │  LLM Provider│  │
│  │  - KNN         │  │ - Intent Detect│  │  - Gemini API│  │
│  │  - KR          │  │ - Conversation │  │  - Chat Gen  │  │
│  │  - LWLR        │  │ - Personalize  │  │  - Retry/Log │  │
│  └────────────────┘  └────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ PostgreSQL   │  │    Redis     │  │  External APIs   │  │
│  │ - User data  │  │ - Sessions   │  │  - Gemini API    │  │
│  │ - Scores     │  │ - Cache      │  │                  │  │
│  │ - ML samples │  │              │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                  MONITORING LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Prometheus   │  │   Grafana    │  │  Loki + Promtail │  │
│  │ - Metrics    │  │ - Dashboards │  │  - Logs          │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2. Luồng dữ liệu chính

**A. Dự đoán điểm số:**
```
User Input → API Endpoint → Prediction Service → ML Algorithm 
→ Database Update → WebSocket Notification → UI Update
```

**B. Chatbot conversation:**
```
User Message → WebSocket/API → Intent Detection → Chatbot Service 
→ Gemini API → Response Generation → Pending Updates (if needed) 
→ WebSocket → Chat UI
```

**C. Import dataset:**
```
Excel File → Upload Endpoint → Excel Importer → Data Validation 
→ Database Insert → ML Pipeline Trigger → Recalculate Predictions
```

---

## 🧩 CÁC THÀNH PHẦN CHÍNH

### 3.1. Frontend (React + Vite)

**Công nghệ:**
- React 19.2.0 - UI framework
- Vite 7.2.4 - Build tool & dev server
- React Router 7.9.6 - Client-side routing
- Chart.js 4.5.1 & Recharts 3.4.1 - Data visualization
- Socket.IO Client 4.8.1 - Real-time communication
- Axios 1.13.2 - HTTP client
- React Markdown 10.1.0 - Markdown rendering
- Framer Motion 12.23.24 - Animations

**Cấu trúc thư mục:**
```
frontend_react/
├── src/
│   ├── pages/          # Các trang chính
│   │   ├── Auth.jsx           # Đăng nhập/đăng ký
│   │   ├── FirstLogin.jsx     # Onboarding cho user mới
│   │   ├── Chatbot.jsx        # Giao diện chatbot
│   │   ├── DataViz.jsx        # Dashboard & biểu đồ
│   │   ├── StudyUpdate.jsx    # Cập nhật điểm
│   │   ├── LearningGoals.jsx  # Quản lý mục tiêu
│   │   ├── Settings.jsx       # Cài đặt tài khoản
│   │   └── Developer.jsx      # Quản trị ML
│   ├── components/     # Components tái sử dụng
│   │   ├── Layout.jsx         # Layout chung
│   │   └── NotificationBell.jsx
│   ├── context/        # React Context
│   │   ├── AuthContext.jsx    # Quản lý authentication
│   │   └── WebSocketContext.jsx # Quản lý WebSocket
│   ├── api/            # API client
│   │   └── axiosClient.js
│   ├── utils/          # Utilities
│   │   ├── eventBus.js        # Event emitter
│   │   └── validation.js
│   └── App.jsx         # Root component
├── public/             # Static assets
├── Dockerfile          # Development Docker image
├── Dockerfile.prod     # Production Docker image
└── package.json
```

**Tính năng chính:**

1. **Authentication & Authorization:**
   - JWT-based authentication
   - Protected routes
   - Role-based access (user/developer/admin)
   - First-time login flow

2. **Real-time Communication:**
   - WebSocket connection via Socket.IO
   - Live chat updates
   - Score prediction notifications
   - Typing indicators

3. **Data Visualization:**
   - Line charts: Xu hướng điểm theo thời gian
   - Bar charts: So sánh actual vs predicted
   - Radar charts: Phân tích đa môn học
   - Progress tracking
   - Benchmark comparisons

4. **Chatbot Interface:**
   - Multi-session support
   - Markdown rendering
   - Pending confirmation UI
   - Score update suggestions
   - Profile editing via chat

5. **Developer Dashboard:**
   - ML model selection (KNN/KR/LWLR)
   - Parameter tuning
   - Dataset upload (Excel)
   - Model evaluation & metrics
   - Pipeline management

### 3.2. Backend (FastAPI + Python)

**Công nghệ:**
- FastAPI - Modern web framework
- SQLAlchemy - ORM
- PostgreSQL 15 - Relational database
- Redis 7 - Session & caching
- Uvicorn/Gunicorn - ASGI server
- Socket.IO - WebSocket support
- Prometheus Client - Metrics
- Python JSON Logger - Structured logging

**Machine Learning Stack:**
- scikit-learn - ML algorithms & utilities
- numpy - Numerical computing
- scipy - Scientific computing
- pandas - Data manipulation

**Cấu trúc thư mục:**
```
backend/
├── api/                # API route handlers
│   ├── auth.py              # Authentication endpoints
│   ├── chatbot.py           # Chatbot API
│   ├── study.py             # Study scores CRUD
│   ├── learning_goals.py    # Goals management
│   ├── user.py              # User profile
│   └── developer.py         # Admin/developer tools
├── services/           # Business logic
│   ├── chatbot_service.py       # Chat orchestration
│   ├── llm_provider.py          # Gemini API integration
│   ├── intent_detection.py      # NLP intent parsing
│   ├── personalization_learner.py
│   ├── educational_knowledge.py # Domain knowledge
│   ├── excel_importer.py        # Dataset import
│   ├── dataset_analyzer.py      # Statistical analysis
│   ├── model_evaluator.py       # ML model evaluation
│   └── ml_version_manager.py    # Version tracking
├── ml/                 # Machine Learning
│   ├── prediction_service.py    # Main prediction engine
│   └── knn_common.py            # Feature engineering
├── core/               # Core utilities
│   ├── logging_config.py        # Structured logging
│   ├── metrics.py               # Prometheus metrics
│   ├── metrics_collector.py     # System metrics
│   ├── websocket_manager.py     # WebSocket handling
│   └── study_constants.py       # Domain constants
├── db/                 # Database
│   ├── database.py              # DB connection
│   └── models.py                # SQLAlchemy models
├── utils/              # Utilities
│   └── session_utils.py         # Session management
├── alembic/            # Database migrations
└── main.py             # Application entry point
```

**Database Schema (PostgreSQL):**

```sql
-- Users table
users:
  - id (PK)
  - username (unique)
  - hashed_password
  - first_name, last_name, email, phone, address, age
  - preferences (JSON)
  - current_grade
  - role (user/developer/admin)
  - first_login_completed
  - ml_config_version

-- Study scores table
study_scores:
  - id (PK)
  - user_id (FK)
  - subject, grade_level, semester
  - actual_score, predicted_score
  - actual_source, predicted_source
  - actual_status, predicted_status
  - actual_updated_at, predicted_updated_at
  - UNIQUE(user_id, subject, grade_level, semester)

-- KNN reference samples (shared dataset)
knn_reference_samples:
  - id (PK)
  - feature_data (JSON) - all subject scores
  - user_id (FK, nullable) - for future user-specific data
  - source, metadata

-- Chat sessions
chat_sessions:
  - id (PK)
  - user_id (FK)
  - title
  - created_at, updated_at

-- Chat messages
chat_messages:
  - id (PK)
  - session_id (FK)
  - role (user/assistant/system)
  - content (text)
  - metadata (JSON)
  - created_at

-- Pending updates (for chat confirmations)
pending_updates:
  - id (PK)
  - user_id (FK)
  - update_type (profile/score/document)
  - field, old_value, new_value
  - metadata (JSON)
  - created_at

-- ML model configuration
ml_model_configs:
  - id (PK)
  - active_model (knn/kernel_regression/lwlr)
  - version
  - updated_by (FK)
  - updated_at

-- Model parameters
model_parameters:
  - id (PK)
  - knn_n (default: 15)
  - kr_bandwidth (default: 1.25)
  - lwlr_tau (default: 3.0)
  - version
  - updated_by (FK)
  - updated_at

-- Learning goals
learning_goals:
  - id (PK)
  - user_id (FK)
  - title, description
  - target_date, priority, status
  - metadata (JSON)

-- Data import logs
data_import_logs:
  - id (PK)
  - uploaded_by (FK)
  - filename
  - total_rows, imported_rows, skipped_rows
  - error_message, metadata
  - created_at
```

---

## 🤖 MACHINE LEARNING - 3 MÔ HÌNH DỰ ĐOÁN

### 4.1. Tổng quan ML Pipeline

**Input:** Điểm số hiện tại của học sinh (actual scores)  
**Output:** Điểm dự đoán cho các môn/kỳ chưa có điểm  
**Dataset:** Reference samples từ KNNReferenceSample table (shared)

**Feature Engineering:**
- Feature key format: `{subject}|{semester}|{grade}`
- Ví dụ: `Toan|1|10` (Toán học kỳ 1 lớp 10)
- Tổng features: 9 môn × 2 học kỳ × 3 lớp = 54 features/sample

### 4.2. Mô hình 1: K-Nearest Neighbors (KNN)

**File:** `backend/ml/prediction_service.py` - `_predict_with_knn()`

**Nguyên lý:**
- Tìm k láng giềng gần nhất dựa trên Euclidean distance
- Dự đoán = weighted average của điểm số k láng giềng
- Weight = 1 / (distance + ε) để tránh division by zero

**Thuật toán:**
```python
for each target_key:
    neighbors = []
    for sample in dataset:
        # Calculate Euclidean distance based on overlapping features
        overlap = actual_keys ∩ sample.keys()
        distance = sqrt(Σ(sample[key] - actual[key])² for key in overlap)
        neighbors.append((distance, sample))
    
    # Sort and select top k
    neighbors.sort(by distance)
    top_k = neighbors[:k]
    
    # Weighted prediction
    numerator = Σ(weight_i × value_i)
    denominator = Σ(weight_i)
    prediction = numerator / denominator
```

**Tham số:**
- `knn_n`: Số láng giềng (default: 15)
- Có thể điều chỉnh qua Developer Dashboard

**Ưu điểm:**
- Đơn giản, dễ hiểu
- Không cần training phase
- Hoạt động tốt với small-medium datasets

**Nhược điểm:**
- Sensitive to k selection
- Tốn computational cost khi predict

### 4.3. Mô hình 2: Kernel Regression (Nadaraya-Watson)

**File:** `backend/ml/prediction_service.py` - `_predict_with_kernel_regression()`

**Nguyên lý:**
- Sử dụng Gaussian kernel để weight tất cả samples
- Không giới hạn k neighbors, sử dụng toàn bộ dataset
- Kernel function: K(x) = exp(-d²/(2σ²))

**Thuật toán:**
```python
for each target_key:
    numerator = 0
    denominator = 0
    
    for sample in dataset:
        # Calculate Euclidean distance
        distance = euclidean(actual_vec, sample_vec)
        
        # Gaussian kernel weight
        weight = exp(-(distance²) / (2 × bandwidth²))
        
        numerator += weight × sample[target_key]
        denominator += weight
    
    prediction = numerator / denominator
```

**Tham số:**
- `kr_bandwidth` (σ): Kernel bandwidth (default: 1.25)
- Bandwidth càng lớn → smooth hơn, ít sensitive với outliers
- Bandwidth càng nhỏ → fit chặt hơn, dễ overfit

**Ưu điểm:**
- Smooth predictions
- Sử dụng toàn bộ thông tin từ dataset
- Robust với noise

**Nhược điểm:**
- Slower than KNN (compute tất cả samples)
- Sensitive to bandwidth parameter

### 4.4. Mô hình 3: Locally Weighted Linear Regression (LWLR)

**File:** `backend/ml/prediction_service.py` - `_predict_with_lwlr()`

**Nguyên lý:**
- Kết hợp KNN và Linear Regression
- Tìm k láng giềng gần nhất, sau đó fit weighted linear regression
- Sử dụng tricube kernel để tính weights

**Thuật toán:**
```python
for each target_key:
    # Find k nearest neighbors that have target_key
    neighbors = find_k_nearest(actual_map, dataset, k)
    
    # Calculate bandwidth from max distance
    max_distance = neighbors[-1].distance
    bandwidth = max_distance / tau
    
    # Compute tricube weights
    for neighbor in neighbors:
        normalized_dist = distance / bandwidth
        if normalized_dist < 1.0:
            weight = (1 - normalized_dist³)³
        else:
            weight = 0.0
    
    # Fit weighted linear regression
    lr = LinearRegression()
    lr.fit(X_neighbors, y_neighbors, sample_weight=weights)
    
    # Predict
    prediction = lr.predict(actual_vec)
```

**Tham số:**
- `lwlr_tau`: Điều chỉnh window size (default: 3.0)
- Tau càng lớn → bandwidth càng nhỏ → locality càng mạnh
- Tau càng nhỏ → bandwidth càng lớn → global hơn

**Ưu điểm:**
- Capture linear trends trong local regions
- Flexible, adaptive to data structure
- Tốt cho non-linear relationships

**Nhược điểm:**
- Computationally expensive (fit LR mỗi prediction)
- Cần ít nhất 2 neighbors để fit regression
- Sensitive to tau parameter

### 4.5. Model Evaluation System

**File:** `backend/services/model_evaluator.py`

**2 Evaluation Tasks:**

1. **Task 1:** Predict Grade 12 from Grades 10-11
   - Input features: 36 scores (9 môn × 2 kỳ × 2 lớp)
   - Target features: 18 scores (9 môn × 2 kỳ × lớp 12)

2. **Task 2:** Predict Grade 11 from Grade 10
   - Input features: 18 scores (9 môn × 2 kỳ × lớp 10)
   - Target features: 18 scores (9 môn × 2 kỳ × lớp 11)

**Metrics:**
- **MAE** (Mean Absolute Error): Trung bình độ lệch tuyệt đối
- **MSE** (Mean Squared Error): Trung bình bình phương độ lệch
- **RMSE** (Root Mean Squared Error): Căn bậc 2 của MSE
- **Accuracy@0.5**: % predictions sai số ≤ 0.5 điểm
- **Accuracy@1.0**: % predictions sai số ≤ 1.0 điểm

**Methodology:**
- 80/20 train-test split
- Only use complete records (có đủ input + target)
- Report metrics cho cả 2 tasks và 3 models

**Endpoint:** `/developer/evaluate-models`

---

## 🤖 CHATBOT & GEMINI API INTEGRATION

### 5.1. LLM Provider Service

**File:** `backend/services/llm_provider.py`

**Gemini API Configuration:**
```python
LLM_PROVIDER=gemini
LLM_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
LLM_API_KEY=<your-api-key>
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=90
```

**Features:**
- **Format conversion:** OpenAI-style messages → Gemini contents format
  - `role: "system"` → `role: "user"` (Gemini không hỗ trợ system role)
  - `role: "user"` → `role: "user"`
  - `role: "assistant"` → `role: "model"`

- **Retry mechanism:** 
  - Max retries: 3
  - Exponential backoff: 0.8s × 2^(attempt-1)
  - Auto-retry on 429 (rate limit) và 5xx errors

- **Concurrency control:**
  - Semaphore limit: 6 concurrent requests
  - Prevent API overload

- **Response parsing:**
  - Extract từ `candidates[0].content.parts[0].text`
  - Fallback parsing cho nhiều response formats

- **Metrics tracking:**
  - Request count, duration, errors
  - Token usage (input/output tokens)
  - Exported to Prometheus

### 5.2. Intent Detection

**File:** `backend/services/intent_detection.py`

Hệ thống phát hiện ý định của user từ chat message:

**1. Score Update Intent:**
```python
detect_score_update_intent(message) → ScoreUpdateIntent
```
- Pattern matching: "điểm toán", "môn lý", "học kỳ 1"
- Extract: subject, semester, grade, score value
- Normalize Vietnamese diacritics

**2. Profile Update Intent:**
```python
detect_profile_update_intent(message) → dict
```
- Detect: first_name, last_name, email, phone updates
- Pattern: "tên tôi là", "email của tôi", "số điện thoại"

**3. Personalization Intent:**
```python
detect_personalization_intent(message) → bool
```
- Keywords: "học như thế nào", "phương pháp", "lời khuyên"

**4. Confirmation Intent:**
```python
detect_confirmation_intent(message) → bool
```
- Patterns: "đúng", "ok", "xác nhận", "đồng ý"

**5. Cancellation Intent:**
```python
detect_cancellation_intent(message) → bool
```
- Patterns: "không", "hủy", "thôi", "sai rồi"

### 5.3. Chatbot Service Workflow

**File:** `backend/services/chatbot_service.py`

**Main function:** `generate_chat_response(db, user_id, message, session_id)`

**Workflow:**
```
1. Check pending updates
   ├─ If has pending → Ask for confirmation
   └─ Detect confirmation/cancellation intent

2. Detect score update intent
   ├─ Parse subject/semester/grade/score
   ├─ Validate score (0-10 range)
   ├─ Create pending update
   └─ Ask user to confirm

3. Detect profile update intent
   ├─ Extract field & new value
   ├─ Create pending update
   └─ Ask user to confirm

4. Detect personalization intent
   ├─ Analyze chat session
   └─ Learn preferences (PersonalizationLearner)

5. General conversation
   ├─ Build context from user profile
   ├─ Include study scores & predictions
   ├─ Add dataset benchmark statistics
   ├─ Add educational knowledge
   └─ Call Gemini API with enriched context
```

**Context Building:**
- User profile summary
- Recent study scores (actual + predicted)
- Dataset statistics (mean, median, percentiles)
- Score classifications (Xuất sắc/Giỏi/Khá/Trung bình)
- GPA calculations
- Learning preferences

### 5.4. Personalization Learner

**File:** `backend/services/personalization_learner.py`

Analyze chat patterns để học preferences:

**Detected Patterns:**
1. **Communication style:**
   - Short messages (<20 chars) → prefer concise answers
   - Long messages (>100 chars) → prefer detailed explanations

2. **Formality level:**
   - Formal words: "xin", "ạ", "dạ", "thưa", "kính"
   - Informal words: "nè", "nhé", "ừ", "oke"

3. **Topic interests:**
   - Study keywords: "học", "điểm", "thi", "ôn", "môn"
   - Goal keywords: "mục tiêu", "kế hoạch", "cần", "muốn"

**Stored in:** `users.preferences` JSON field

---

## 📊 REAL-TIME COMMUNICATION & WEBSOCKET

### 6.1. WebSocket Manager

**File:** `backend/core/websocket_manager.py`

**Technology:** Socket.IO (async mode with ASGI)

**Connection Management:**
```python
# Track connections
user_sessions: Dict[user_id → Set[session_ids]]
session_users: Dict[session_id → user_id]
```

**Event Handlers:**

1. **connect:** Client kết nối
   - Extract user_id from auth
   - Track session
   - Send connection confirmation

2. **disconnect:** Client ngắt kết nối
   - Remove from tracking
   - Cleanup resources

3. **join_chat_session:** Join chat room
   - User joins specific chat session room
   - Receive messages for that session only

4. **leave_chat_session:** Leave chat room
   - User leaves session room

**Emit Functions:**

```python
# Emit to all sessions of a user
emit_to_user(user_id, event, data)

# Emit to specific session
emit_to_session(session_id, event, data)

# Broadcast to all clients
broadcast(event, data)
```

### 6.2. Real-time Events

**Frontend WebSocket Context:** `frontend_react/src/context/WebSocketContext.jsx`

**Events:**

1. **chat_message:** New chat message
   ```json
   {
     "session_id": "123",
     "role": "assistant",
     "message": "Xin chào!"
   }
   ```

2. **chat_typing:** Typing indicator
   ```json
   {
     "session_id": "123",
     "is_typing": true
   }
   ```

3. **study_update:** Score updated
   ```json
   {
     "user_id": 1,
     "score": {...}
   }
   ```

4. **prediction_update:** New prediction available
   ```json
   {
     "user_id": 1,
     "predictions": [...]
   }
   ```

5. **notification:** General notification
   ```json
   {
     "type": "info",
     "message": "..."
   }
   ```

---

## 📈 MONITORING & OBSERVABILITY

### 7.1. Prometheus Metrics

**File:** `backend/core/metrics.py`

**HTTP Metrics:**
- `http_requests_total`: Counter by method/endpoint/status
- `http_request_duration_seconds`: Histogram of request latency
- `http_requests_in_progress`: Gauge of concurrent requests

**LLM Metrics:**
- `llm_requests_total`: Counter by provider/model/status
- `llm_request_duration_seconds`: LLM API latency
- `llm_tokens_total`: Token usage (input/output)
- `llm_errors_total`: Error count by type
- `llm_retries_total`: Retry count

**ML Metrics:**
- `ml_predictions_total`: Prediction count by model
- `ml_prediction_duration_seconds`: Prediction latency
- `ml_dataset_size`: Number of reference samples

**System Metrics:**
- `python_info`: Python version
- `process_cpu_seconds_total`: CPU time
- `process_resident_memory_bytes`: Memory usage

**Endpoint:** `http://backend:8000/metrics`

### 7.2. Structured Logging

**File:** `backend/core/logging_config.py`

**Format:** JSON logs via `python-json-logger`

**Fields:**
- timestamp
- level (INFO/WARNING/ERROR)
- logger name
- message
- extra context (user_id, endpoint, duration, etc.)

**Outputs:**
- Console (for Docker logs)
- Captured by Promtail → Loki

### 7.3. Grafana Dashboards

**Location:** `grafana/dashboards/`

1. **edutwin-dashboard.json:**
   - HTTP request rate & latency
   - Error rate
   - LLM API usage & costs
   - ML prediction performance
   - Active users/sessions

2. **logs-dashboard.json:**
   - Log volume by level
   - Error logs table
   - Slow request alerts

**Access:** `http://localhost:3001` (default credentials: admin/admin)

---

## 🔐 SECURITY & AUTHENTICATION

### 8.1. Authentication Flow

**Technology:** JWT (JSON Web Tokens)

**File:** `backend/api/auth.py`

**Endpoints:**
- `POST /auth/register`: Tạo tài khoản mới
- `POST /auth/login`: Đăng nhập → nhận access token
- `GET /auth/me`: Lấy thông tin user hiện tại

**Password Security:**
- Hashing: bcrypt (cost factor: 12)
- Never store plaintext passwords
- Validate password strength

**Session Management:**
- Redis-based session storage
- Session timeout: configurable
- Session invalidation on logout

### 8.2. Authorization

**Roles:**
- `user`: Regular student (default)
- `developer`: Can access ML configuration
- `admin`: Full system access

**Protected Endpoints:**
- `@require_auth`: Requires valid JWT
- `@require_role("developer")`: Role-based access

**Frontend Protection:**
- ProtectedRoute component
- Redirect to login if unauthenticated
- Hide developer features from regular users

---

## 🚀 DEPLOYMENT

### 9.1. Docker Architecture

**File:** `docker-compose.yml`

**Services:**

1. **db** (PostgreSQL 15)
   - Port: 5432
   - Volume: postgres_data
   - Healthcheck enabled

2. **adminer** (Database UI)
   - Port: 8081
   - Web-based DB management

3. **redis** (Cache & Sessions)
   - Port: 6379

4. **backend** (FastAPI)
   - Port: 8000
   - Depends on: db, redis
   - Dev mode: Hot reload với volume mount
   - Prod mode: Gunicorn workers

5. **frontend** (React + Nginx)
   - Port: 3000
   - Dev mode: Vite dev server
   - Prod mode: Nginx serve static build

6. **prometheus** (Metrics)
   - Port: 9090
   - Scrape backend metrics

7. **grafana** (Dashboards)
   - Port: 3001
   - Pre-configured dashboards

8. **loki** (Log aggregation)
   - Port: 3100

9. **promtail** (Log shipper)
   - Collect Docker logs → Loki

**Networks:** edutwin_network (bridge)

### 9.2. Environment Variables

**File:** `.env`

```bash
# Database
POSTGRES_DB=edutwin
POSTGRES_USER=edutwin_user
POSTGRES_PASSWORD=edutwin_password_2024
DATABASE_URL=postgresql://edutwin_user:edutwin_password_2024@db:5432/edutwin

# Redis
REDIS_URL=redis://redis:6379

# Security
SECRET_KEY=edutwin_2024_secure_key_32_chars_long_random_string_here

# Gemini API
LLM_PROVIDER=gemini
LLM_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
LLM_API_KEY=<your-gemini-api-key>
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=90

# Logging
LOG_LEVEL=INFO

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=http://localhost:8000/ws
```

### 9.3. Commands

**Development:**
```powershell
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend

# Restart specific service
docker compose restart backend

# Stop all
docker compose down
```

**Production:**
```powershell
# Build production images
docker compose -f docker-compose.prod.yml build

# Deploy
docker compose -f docker-compose.prod.yml up -d
```

**Database migrations:**
```powershell
# Generate migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec backend alembic upgrade head
```

---

## 📚 API ENDPOINTS

### 10.1. Authentication
- `POST /auth/register` - Đăng ký
- `POST /auth/login` - Đăng nhập
- `GET /auth/me` - Thông tin user
- `POST /auth/logout` - Đăng xuất

### 10.2. User Profile
- `GET /user/profile` - Lấy profile
- `PUT /user/profile` - Cập nhật profile
- `PUT /user/preferences` - Cập nhật preferences

### 10.3. Study Scores
- `GET /study/scores` - Lấy tất cả điểm
- `GET /study/scores/{id}` - Lấy điểm cụ thể
- `POST /study/scores` - Thêm/cập nhật điểm
- `DELETE /study/scores/{id}` - Xóa điểm
- `GET /study/structure` - Lấy cấu trúc môn học
- `POST /study/update-score` - Cập nhật điểm đơn

### 10.4. Predictions
- `POST /study/predict` - Trigger prediction cho user
- `GET /study/predictions` - Lấy predictions

### 10.5. Chatbot
- `GET /chatbot/sessions` - Lấy danh sách chat sessions
- `POST /chatbot/sessions` - Tạo session mới
- `DELETE /chatbot/sessions/{id}` - Xóa session
- `GET /chatbot/sessions/{id}/messages` - Lấy messages
- `POST /chatbot/chat` - Gửi message
- `GET /chatbot/pending-updates` - Lấy pending confirmations
- `POST /chatbot/confirm-update/{id}` - Confirm update
- `POST /chatbot/cancel-update/{id}` - Cancel update

### 10.6. Learning Goals
- `GET /learning-goals` - Lấy danh sách mục tiêu
- `POST /learning-goals` - Tạo mục tiêu mới
- `PUT /learning-goals/{id}` - Cập nhật mục tiêu
- `DELETE /learning-goals/{id}` - Xóa mục tiêu

### 10.7. Developer (Admin only)
- `POST /developer/upload-dataset` - Upload Excel dataset
- `GET /developer/dataset-summary` - Xem thống kê dataset
- `POST /developer/run-pipeline` - Chạy ML pipeline
- `POST /developer/evaluate-models` - Đánh giá models
- `GET /developer/model-status` - Xem model hiện tại
- `POST /developer/select-model` - Chọn model (KNN/KR/LWLR)
- `GET /developer/parameters` - Lấy parameters
- `POST /developer/parameters` - Cập nhật parameters

---

## 🎓 DOMAIN KNOWLEDGE

### 11.1. Score Classification

**File:** `backend/services/educational_knowledge.py`

```python
Điểm 9.0-10.0: Xuất sắc
Điểm 8.0-8.9: Giỏi
Điểm 6.5-7.9: Khá
Điểm 5.0-6.4: Trung bình
Điểm 3.5-4.9: Yếu
Điểm 0.0-3.4: Kém
```

### 11.2. GPA Classification

```python
GPA 9.0-10.0: Xuất sắc
GPA 8.0-8.9: Giỏi
GPA 6.5-7.9: Khá
GPA 5.0-6.4: Trung bình
GPA < 5.0: Yếu
```

### 11.3. Subjects (9 môn)

```python
SUBJECTS = [
    "Toan",           # Toán
    "Ngu van",        # Ngữ văn
    "Vat ly",         # Vật lý
    "Hoa hoc",        # Hóa học
    "Sinh hoc",       # Sinh học
    "Lich su",        # Lịch sử
    "Dia ly",         # Địa lý
    "Tieng Anh",      # Tiếng Anh
    "Giao duc cong dan"  # GDCD
]
```

### 11.4. Grade Levels & Semesters

```python
GRADE_ORDER = ["10", "11", "12", "TN"]

SEMESTER_ORDER = {
    "10": ["1", "2"],
    "11": ["1", "2"],
    "12": ["1", "2"],
    "TN": ["TN"]  # Kỳ thi tốt nghiệp
}
```

### 11.5. Exam Blocks (Khối thi)

```python
A00: Toán, Vật lý, Hóa học
B00: Toán, Hóa học, Sinh học
C00: Ngữ văn, Lịch sử, Địa lý
D01: Toán, Ngữ văn, Tiếng Anh
```

---

## 📊 DATASET FORMAT

### 12.1. Excel Import Format

**File:** Upload qua Developer Dashboard

**Required columns:**
- Subject_Semester_Grade format
- Example: `Toan_1_10`, `Vat ly_2_11`, `Ngu van_TN_12`

**Valid values:**
- Scores: 0.0 - 10.0
- Empty cells: Skip

**Sample Excel structure:**
```
| Toan_1_10 | Toan_2_10 | Ly_1_10 | ... | Toan_TN_12 |
|-----------|-----------|---------|-----|------------|
| 8.5       | 8.7       | 7.2     | ... | 8.9        |
| 9.0       | 9.2       | 8.5     | ... | 9.1        |
```

### 12.2. Feature Data Structure

**Stored in:** `knn_reference_samples.feature_data` (JSON)

```json
{
  "Toan|1|10": 8.5,
  "Toan|2|10": 8.7,
  "Vat ly|1|10": 7.2,
  "Hoa hoc|1|10": 8.0,
  ...
  "Toan|TN|12": 8.9
}
```

---

## 🔧 CONFIGURATION & TUNING

### 13.1. ML Model Parameters

**Adjustable via Developer Dashboard:**

1. **KNN:**
   - `knn_n`: Number of neighbors (default: 15)
   - Range: 1-50
   - Recommendation: 10-20 for small datasets

2. **Kernel Regression:**
   - `kr_bandwidth`: Gaussian kernel sigma (default: 1.25)
   - Range: 0.1-5.0
   - Higher = smoother predictions

3. **LWLR:**
   - `lwlr_tau`: Window size control (default: 3.0)
   - Range: 0.5-10.0
   - Higher = more local, lower = more global

**Versioning:**
- Each parameter change increments version
- Users marked for re-prediction when version changes
- ML version tracking ensures consistency

### 13.2. LLM Configuration

**Gemini API Settings:**
- Temperature: 0.2 (deterministic)
- Max output tokens: 8096
- Timeout: 90 seconds
- Max retries: 3
- Concurrency limit: 6

**Customizable in code:**
- `backend/services/llm_provider.py`
- Adjust temperature for creativity
- Increase timeout for complex queries

---

## 🎯 KEY FEATURES SUMMARY

1. ✅ **Machine Learning Predictions**
   - 3 models: KNN, Kernel Regression, LWLR
   - Real-time predictions
   - Model comparison & evaluation
   - Parameter tuning

2. ✅ **AI Chatbot**
   - Gemini 2.5 Flash integration
   - Intent detection
   - Score updates via chat
   - Profile editing via chat
   - Personalization learning

3. ✅ **Data Visualization**
   - Multi-chart support (Line, Bar, Radar)
   - Actual vs Predicted comparison
   - Benchmark analysis
   - Progress tracking

4. ✅ **Real-time Updates**
   - WebSocket communication
   - Live notifications
   - Typing indicators
   - Multi-session sync

5. ✅ **Developer Tools**
   - Dataset upload (Excel)
   - Model evaluation metrics
   - Pipeline management
   - Parameter configuration

6. ✅ **Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Structured logging
   - Performance tracking

7. ✅ **Security**
   - JWT authentication
   - Role-based access
   - Password hashing (bcrypt)
   - Session management

---

## 📖 REFERENCES

### Technologies Used:
- **Frontend:** React, Vite, Chart.js, Recharts, Socket.IO
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, Redis
- **ML:** scikit-learn, numpy, scipy, pandas
- **AI:** Google Gemini API
- **DevOps:** Docker, Docker Compose
- **Monitoring:** Prometheus, Grafana, Loki, Promtail

### Documentation:
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- Gemini API: https://ai.google.dev/
- Socket.IO: https://socket.io/
- scikit-learn: https://scikit-learn.org/

---

**Tài liệu này được tạo tự động từ source code của EduTwin.**  
**Ngày tạo:** November 30, 2025  
**Phiên bản:** 1.0.0
