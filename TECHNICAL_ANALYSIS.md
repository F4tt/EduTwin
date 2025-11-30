# EDUTWIN - PHÂN TÍCH KỸ THUẬT CHI TIẾT

## 📋 MỤC LỤC

1. [Sơ đồ luồng nghiệp vụ chi tiết](#1-sơ-đồ-luồng-nghiệp-vụ-chi-tiết)
2. [Hướng dẫn sử dụng từng tính năng](#2-hướng-dẫn-sử-dụng-từng-tính-năng)
3. [Screenshots mô phỏng](#3-screenshots-mô-phỏng)
4. [Kết quả đánh giá mô hình](#4-kết-quả-đánh-giá-mô-hình)
5. [Phân tích kỹ thuật sâu](#5-phân-tích-kỹ-thuật-sâu)

---

## 1. SƠ ĐỒ LUỒNG NGHIỆP VỤ CHI TIẾT

### 1.1. Luồng Đăng ký & Đăng nhập

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                       │
└─────────────────────────────────────────────────────────────┘

[User] → Access Website
           ↓
    ┌──────────────┐
    │ Landing Page │
    └──────────────┘
           ↓
    ┌──────────────┐
    │  Login Form  │
    └──────────────┘
           ↓
    Has account? ──No──→ [Register]
           │                  ↓
          Yes          1. Enter username
           ↓           2. Enter password
    1. Enter creds    3. Validate (min 6 chars)
    2. Submit              ↓
           ↓           POST /auth/register
    POST /auth/login       ↓
           ↓           ┌──────────────────────┐
    ┌─────────────────┤ Backend validates:   │
    │                 │ - Username unique?   │
    │                 │ - Password strength  │
    │                 └──────────────────────┘
    ↓                          ↓
[Success]                 [Hash password]
    ↓                      (bcrypt, cost=12)
Generate JWT                   ↓
    ↓                   Create User record
Set token in           first_login_completed=False
localStorage                   ↓
    ↓                    Return user data
Redirect based on             ↓
first_login flag      [Auto login with token]
    ↓                          ↓
┌─────────────────────────────────────┐
│ first_login_completed = False?      │
│  Yes → /first-time (Onboarding)     │
│  No  → /chat (Main app)             │
└─────────────────────────────────────┘
```

### 1.2. Luồng First-time Onboarding

```
┌─────────────────────────────────────────────────────────────┐
│                   FIRST LOGIN ONBOARDING                     │
└─────────────────────────────────────────────────────────────┘

[New User] → /first-time page
                ↓
    ┌───────────────────────────┐
    │  Welcome Screen           │
    │  "Chào mừng đến EduTwin!" │
    └───────────────────────────┘
                ↓
    ┌───────────────────────────┐
    │  Step 1: Personal Info    │
    │  - First name             │
    │  - Last name              │
    │  - Email (optional)       │
    │  - Phone (optional)       │
    │  - Age (optional)         │
    └───────────────────────────┘
                ↓
    ┌───────────────────────────┐
    │  Step 2: Academic Info    │
    │  - Current grade (10/11/12) required│
    └───────────────────────────┘
                ↓
    ┌───────────────────────────┐
    │  Step 3: Preferences      │
    │  - Learning style         │
    │  - Favorite subjects      │
    │  - Study goals            │
    └───────────────────────────┘
                ↓
        [Submit All Data]
                ↓
    POST /user/complete-first-login
                ↓
    ┌───────────────────────────┐
    │ Backend updates:          │
    │ - User profile fields     │
    │ - preferences JSON        │
    │ - first_login_completed   │
    │   = True                  │
    └───────────────────────────┘
                ↓
    [Redirect to /chat]
                ↓
        Main Application
```

### 1.3. Luồng Cập nhật Điểm số (Manual Input)

```
┌─────────────────────────────────────────────────────────────┐
│                    SCORE UPDATE FLOW                         │
└─────────────────────────────────────────────────────────────┘

[User] → Navigate to /study
            ↓
    ┌───────────────────────┐
    │  Study Update Page    │
    │  Display score matrix │
    └───────────────────────┘
            ↓
    GET /study/scores
            ↓
    ┌───────────────────────────────────┐
    │ Backend returns:                  │
    │ - All study_scores for user       │
    │ - Organized by grade/semester     │
    │ - Both actual & predicted values  │
    └───────────────────────────────────┘
            ↓
    ┌───────────────────────┐
    │  Render Score Grid    │
    │  Rows: Subjects (9)   │
    │  Cols: Terms (6 ) │
    └───────────────────────┘
            ↓
    [User clicks on cell]
            ↓
    ┌───────────────────────┐
    │  Modal opens          │
    │  Input score (0-10)   │
    └───────────────────────┘
            ↓
    [User enters score]
            ↓
    Validate: 0 ≤ score ≤ 10
            ↓
    POST /study/update-score
    {
      subject: "Toan",
      semester: "1",
      grade_level: "10",
      actual_score: 8.5
    }
            ↓
    ┌────────────────────────────────────┐
    │ Backend:                           │
    │ 1. Find or create StudyScore       │
    │ 2. Update actual_score             │
    │ 3. Set actual_source = "manual"    │
    │ 4. Set actual_status = "confirmed" │
    │ 5. Update actual_updated_at        │
    │ 6. Save to database                │
    └────────────────────────────────────┘
            ↓
    ┌────────────────────────────────────┐
    │ Emit WebSocket event:              │
    │ emit_study_update(user_id, score)  │
    └────────────────────────────────────┘
            ↓
    ┌────────────────────────────────────┐
    │ Trigger ML Prediction Pipeline:    │
    │ update_predictions_for_user()      │
    └────────────────────────────────────┘
            ↓
    ┌────────────────────────────────────┐
    │ ML Pipeline:                       │
    │ 1. Load all user's actual scores   │
    │ 2. Load reference dataset          │
    │ 3. Identify missing scores         │
    │ 4. Get active model (KNN/KR/LWLR)  │
    │ 5. Get model parameters            │
    │ 6. Run prediction algorithm        │
    │ 7. Update predicted_score fields   │
    │ 8. Set predicted_source = model    │
    │ 9. Set predicted_updated_at        │
    │ 10. Commit to database             │
    └────────────────────────────────────┘
            ↓
    ┌────────────────────────────────────┐
    │ Emit WebSocket event:              │
    │ emit_prediction_update(user_id)    │
    └────────────────────────────────────┘
            ↓
    ┌────────────────────────────────────┐
    │ Frontend receives events:          │
    │ 1. study_update → refresh scores   │
    │ 2. prediction_update → show new    │
    │    predictions                     │
    └────────────────────────────────────┘
            ↓
    [UI updates automatically]
    - Green highlight for new actual
    - Blue highlight for new predictions
```

### 1.4. Luồng Chatbot Conversation

```
┌─────────────────────────────────────────────────────────────┐
│                    CHATBOT FLOW                              │
└─────────────────────────────────────────────────────────────┘

[User] → Navigate to /chat
            ↓
    GET /chatbot/sessions
            ↓
    ┌───────────────────────┐
    │ Load chat sessions    │
    │ - Most recent first   │
    └───────────────────────┘
            ↓
    Select session or create new
            ↓
    Join WebSocket room
    (socket.emit('join_chat_session', session_id))
            ↓
    GET /chatbot/sessions/{id}/messages
            ↓
    Display chat history
            ↓
┌─────────────────────────────────────────────────────────────┐
│                   USER SENDS MESSAGE                         │
└─────────────────────────────────────────────────────────────┘
            ↓
    [User types message]
            ↓
    [User clicks Send]
            ↓
    POST /chatbot/chat
    {
      session_id: "123",
      message: "Điểm toán học kỳ 1 của tôi là 8.5"
    }
            ↓
┌─────────────────────────────────────────────────────────────┐
│              BACKEND CHATBOT SERVICE                         │
└─────────────────────────────────────────────────────────────┘
            ↓
    1. Save user message to DB
            ↓
    2. Emit typing indicator
       (WebSocket: chat_typing)
            ↓
    3. Check pending updates
       GET pending_updates WHERE user_id
            ↓
    ┌──────────────────────────┐
    │ Has pending updates?     │
    └──────────────────────────┘
       ↓Yes              ↓No
    Ask for         Continue to
    confirmation    intent detection
       ↓                  ↓
    Detect:        ┌──────────────────────┐
    - Confirm?     │ Intent Detection:    │
    - Cancel?      │ 1. Score update?     │
       ↓           │ 2. Profile update?   │
    Apply/Cancel   │ 3. Personalization?  │
    update         │ 4. General question? │
       ↓           └──────────────────────┘
    Generate              ↓
    response       ┌──────────────────────┐
       ↓           │ SCORE UPDATE INTENT  │
    [Done]         └──────────────────────┘
                          ↓
                   Regex patterns:
                   - "điểm (toán|lý|...)"
                   - "(môn) (subject)"
                   - "học kỳ (1|2)"
                   - "lớp (10|11|12)"
                   - score value (0-10)
                          ↓
                   Extract:
                   - subject: "Toan"
                   - semester: "1"
                   - grade: "10"
                   - score: 8.5
                          ↓
                   Validate score range
                          ↓
                   Create PendingUpdate:
                   {
                     user_id: 1,
                     update_type: "score",
                     new_value: "8.5",
                     metadata: {
                       subject, semester, grade
                     }
                   }
                          ↓
                   Generate confirmation:
                   "Tôi hiểu bạn muốn cập nhật
                    điểm Toán HK1 lớp 10 là 8.5.
                    Xác nhận không?"
                          ↓
                   [Send response]
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              USER CONFIRMS                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
                   "Đúng rồi" / "OK"
                          ↓
                   Detect confirmation intent
                          ↓
                   Apply pending update:
                   1. Get pending update
                   2. Update study_score
                   3. Set actual_source="chat"
                   4. Set actual_status="confirmed"
                   5. Delete pending update
                   6. Trigger ML prediction
                          ↓
                   Generate response:
                   "Đã cập nhật điểm Toán!"
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              GENERAL CONVERSATION                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
                   No specific intent detected
                          ↓
                   Build enriched context:
                          ↓
    ┌──────────────────────────────────────┐
    │ Context includes:                    │
    │ 1. User profile                      │
    │    - Name, grade, preferences        │
    │ 2. Study scores                      │
    │    - Recent actual scores            │
    │    - Predicted scores                │
    │    - GPA calculation                 │
    │ 3. Dataset statistics                │
    │    - Mean, median, percentiles       │
    │    - Subject averages                │
    │ 4. Educational knowledge             │
    │    - Score classifications           │
    │    - Study tips by subject           │
    │ 5. Chat history (last 10 messages)   │
    └──────────────────────────────────────┘
                          ↓
    ┌──────────────────────────────────────┐
    │ Format messages for Gemini API:      │
    │ [                                    │
    │   {role: "user", content: system},   │
    │   {role: "user", content: context},  │
    │   {role: "user", content: msg1},     │
    │   {role: "model", content: resp1},   │
    │   ...                                │
    │   {role: "user", content: current}   │
    │ ]                                    │
    └──────────────────────────────────────┘
                          ↓
    POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
                          ↓
    ┌──────────────────────────────────────┐
    │ Gemini API processes:                │
    │ - Understands Vietnamese context     │
    │ - Analyzes educational data          │
    │ - Provides personalized advice       │
    │ - Generates helpful response         │
    └──────────────────────────────────────┘
                          ↓
    Extract response text from:
    candidates[0].content.parts[0].text
                          ↓
    Save assistant message to DB
                          ↓
    Emit via WebSocket:
    emit('chat_message', {
      session_id,
      role: 'assistant',
      message: response
    })
                          ↓
    Frontend receives & displays
```

### 1.5. Luồng Upload Dataset (Developer)

```
┌─────────────────────────────────────────────────────────────┐
│                 DATASET UPLOAD FLOW                          │
└─────────────────────────────────────────────────────────────┘

[Developer] → /developer page
                ↓
    ┌───────────────────────┐
    │ Check authorization   │
    │ role = developer?     │
    └───────────────────────┘
                ↓
    [Select Excel file]
    - Format: .xlsx, .xls
    - Columns: Subject_Semester_Grade
    - Example: Toan_1_10, Ly_2_11
                ↓
    [Click Upload]
                ↓
    POST /developer/upload-dataset
    FormData: file
                ↓
┌─────────────────────────────────────────────────────────────┐
│              BACKEND PROCESSING                              │
└─────────────────────────────────────────────────────────────┘
                ↓
    1. Validate file type
       (.xlsx, .xls only)
                ↓
    2. Read Excel with pandas
       df = pd.read_excel(file)
                ↓
    3. Parse headers
       For each column:
       - Try parse_compound_header()
       - Extract: subject, semester, grade
       - Build feature_key
                ↓
    4. Process rows
       For each row:
       ├─ Create feature_data dict
       ├─ For each column:
       │  ├─ Get cell value
       │  ├─ Validate: 0 ≤ value ≤ 10
       │  ├─ Add to feature_data[key]
       │  └─ Skip if invalid/empty
       └─ If has valid features:
          Create KNNReferenceSample
                ↓
    5. Create DataImportLog
       - filename
       - total_rows
       - imported_rows
       - skipped_rows
       - metadata
                ↓
    6. Commit to database
                ↓
    7. Emit dataset_changed event
                ↓
    8. Run ML pipeline for all users
       (background task)
       ├─ For each user:
       │  └─ update_predictions_for_user()
       └─ Track progress
                ↓
    9. Return summary:
       {
         imported: 150,
         skipped: 5,
         total_samples: 155
       }
                ↓
    Frontend displays success:
    "Đã import 150/155 mẫu thành công"
                ↓
    Auto-refresh dataset statistics
```

### 1.6. Luồng Model Evaluation

```
┌─────────────────────────────────────────────────────────────┐
│              MODEL EVALUATION FLOW                           │
└─────────────────────────────────────────────────────────────┘

[Developer] → Click "Evaluate Models"
                ↓
    POST /developer/evaluate-models
                ↓
┌─────────────────────────────────────────────────────────────┐
│              EVALUATION TASKS                                │
└─────────────────────────────────────────────────────────────┘
                ↓
    Load reference dataset
    (all KNNReferenceSample records)
                ↓
┌───────────────────────────────────────────────────────────┐
│ TASK 1: Predict Grade 12 from Grades 10-11              │
└───────────────────────────────────────────────────────────┘
                ↓
    1. Filter dataset:
       Keep only samples with ALL:
       - 36 input features (grade 10-11)
       - 18 target features (grade 12)
                ↓
    2. Split data:
       - 80% train
       - 20% test
                ↓
    3. For each model (KNN, KR, LWLR):
       ├─ Get current parameters
       ├─ For each test sample:
       │  ├─ Use train set as reference
       │  ├─ Predict 18 grade 12 scores
       │  └─ Compare with actual
       ├─ Calculate metrics:
       │  ├─ MAE = mean(|predicted - actual|)
       │  ├─ MSE = mean((predicted - actual)²)
       │  ├─ RMSE = sqrt(MSE)
       │  ├─ Accuracy@0.5 = % with error ≤ 0.5
       │  └─ Accuracy@1.0 = % with error ≤ 1.0
       └─ Store results
                ↓
┌───────────────────────────────────────────────────────────┐
│ TASK 2: Predict Grade 11 from Grade 10                   │
└───────────────────────────────────────────────────────────┘
                ↓
    Same process but:
    - Input: 18 features (grade 10)
    - Target: 18 features (grade 11)
                ↓
┌───────────────────────────────────────────────────────────┐
│ RETURN COMPARISON RESULTS                                 │
└───────────────────────────────────────────────────────────┘
                ↓
    {
      "task_12_from_10_11": {
        "knn": {mae, mse, rmse, acc_05, acc_10},
        "kernel_regression": {...},
        "lwlr": {...}
      },
      "task_11_from_10": {
        "knn": {...},
        "kernel_regression": {...},
        "lwlr": {...}
      },
      "best_model": "knn",
      "recommendation": "..."
    }
                ↓
    Frontend displays comparison table
    with color-coded best metrics
```

### 1.7. Luồng Model Selection & Parameter Tuning

```
┌─────────────────────────────────────────────────────────────┐
│           MODEL SELECTION & TUNING FLOW                      │
└─────────────────────────────────────────────────────────────┘

[Developer] → Model Settings section
                ↓
    ┌───────────────────────┐
    │ Current status:       │
    │ - Active model: KNN   │
    │ - Version: 5          │
    │ - Parameters:         │
    │   knn_n = 15          │
    │   kr_bandwidth = 1.25 │
    │   lwlr_tau = 3.0      │
    └───────────────────────┘
                ↓
┌─────────────────────────────────────────────────────────────┐
│              CHANGE MODEL                                    │
└─────────────────────────────────────────────────────────────┘
                ↓
    [Select model: Kernel Regression]
                ↓
    POST /developer/select-model
    {model: "kernel_regression"}
                ↓
    Backend:
    1. Update ml_model_configs
       - active_model = "kernel_regression"
       - Increment version
    2. Mark all users for update
       - Reset user.ml_config_version
    3. Trigger pipeline (background)
       - Recalculate all predictions
       - With new model
                ↓
    Emit event: ml_model_changed
                ↓
    Frontend notification:
    "Đã chuyển sang Kernel Regression.
     Đang cập nhật predictions..."
                ↓
┌─────────────────────────────────────────────────────────────┐
│              TUNE PARAMETERS                                 │
└─────────────────────────────────────────────────────────────┘
                ↓
    [Adjust sliders]
    - knn_n: 15 → 20
    - kr_bandwidth: 1.25 → 1.5
    - lwlr_tau: 3.0 → 2.5
                ↓
    [Click Save]
                ↓
    POST /developer/parameters
    {
      knn_n: 20,
      kr_bandwidth: 1.5,
      lwlr_tau: 2.5
    }
                ↓
    Backend:
    1. Update model_parameters
       - Set new values
       - Increment version
    2. Trigger pipeline
       - Recalculate with new params
                ↓
    Emit event: ml_parameters_changed
                ↓
    Frontend notification:
    "Parameters updated. Recalculating..."
```

### 1.8. Luồng Real-time Notification

```
┌─────────────────────────────────────────────────────────────┐
│              WEBSOCKET NOTIFICATION FLOW                     │
└─────────────────────────────────────────────────────────────┘

Backend triggers notification:
                ↓
    emit_notification(user_id, {
      type: "info",
      title: "Cập nhật điểm",
      message: "Điểm Toán đã được cập nhật",
      timestamp: "2025-11-30T10:30:00Z"
    })
                ↓
    WebSocket Manager:
    1. Find all sessions for user_id
    2. For each session:
       socket.emit('notification', data)
                ↓
    Frontend WebSocketContext receives:
                ↓
    useEffect(() => {
      socket.on('notification', (data) => {
        addNotification(data)
      })
    })
                ↓
    NotificationBell component:
    1. Show badge with count
    2. Play notification sound (optional)
    3. Add to notifications list
                ↓
    User clicks bell:
    ├─ Show dropdown
    ├─ List all notifications
    ├─ Mark as read
    └─ Click to navigate
```

### 1.9. Luồng Data Visualization

```
┌─────────────────────────────────────────────────────────────┐
│              DATA VISUALIZATION FLOW                         │
└─────────────────────────────────────────────────────────────┘

[User] → Navigate to /data
            ↓
    GET /study/scores
            ↓
    Backend returns all scores
            ↓
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND DATA PROCESSING                        │
└─────────────────────────────────────────────────────────────┘
            ↓
    1. Group by subject
       subjects = {
         "Toan": [scores...],
         "Vat ly": [scores...],
         ...
       }
            ↓
    2. Sort by term order
       Terms: 1_10, 2_10, 1_11, 2_11, 1_12, 2_12, TN_12
            ↓
    3. Prepare chart data
       For Line Chart:
       {
         labels: ["HK1 L10", "HK2 L10", ...],
         datasets: [
           {
             label: "Actual",
             data: [8.5, null, 8.7, ...],
             color: "green"
           },
           {
             label: "Predicted",
             data: [null, 8.6, null, ...],
             color: "blue"
           }
         ]
       }
            ↓
    4. Render charts:
       ├─ Line Chart: Trend over time
       ├─ Bar Chart: Subject comparison
       ├─ Radar Chart: Multi-subject view
       └─ Progress indicators
            ↓
    5. Calculate statistics:
       ├─ Overall GPA
       ├─ Subject averages
       ├─ Improvement rate
       └─ Predictions accuracy
            ↓
    Display interactive dashboard
```

---

## 2. HƯỚNG DẪN SỬ DỤNG TỪNG TÍNH NĂNG

### 2.1. Đăng ký & Đăng nhập

#### 2.1.1. Đăng ký tài khoản mới

**Bước 1:** Truy cập trang chủ
- URL: `http://localhost:3000`
- Click nút "Đăng ký" hoặc link "Tạo tài khoản"

**Bước 2:** Điền thông tin
```
Username: myusername      (không dấu, 3-50 ký tự)
Password: ••••••••••      (tối thiểu 6 ký tự)
Confirm:  ••••••••••      (nhập lại password)
```

**Bước 3:** Submit
- Click "Đăng ký"
- Hệ thống tự động đăng nhập sau khi đăng ký thành công

**Bước 4:** First-time Setup
- Chuyển tự động đến trang onboarding
- Điền thông tin cá nhân (tên, email, lớp học)
- Thiết lập preferences (tùy chọn)

**Lưu ý:**
- Username phải unique (chưa ai sử dụng)
- Password được mã hóa bằng bcrypt
- Không thể thay đổi username sau khi đăng ký

#### 2.1.2. Đăng nhập

**Cách 1: Form đăng nhập**
```
Username: myusername
Password: ••••••••••
[x] Ghi nhớ đăng nhập (optional)
```

**Cách 2: Auto-login**
- Nếu đã đăng nhập trước đó
- Token lưu trong localStorage
- Tự động authenticate khi mở lại

**Logout:**
- Click vào avatar/username ở header
- Chọn "Đăng xuất"
- Token bị xóa khỏi localStorage

---

### 2.2. Quản lý Điểm số

#### 2.2.1. Xem điểm số

**Truy cập:** Menu → "Điểm số" hoặc `/study`

**Giao diện:**
```
┌─────────────────────────────────────────────────────┐
│  BẢNG ĐIỂM HỌC TẬP                                 │
├─────────┬──────┬──────┬──────┬──────┬──────┬──────┤
│ Môn học │HK1L10│HK2L10│HK1L11│HK2L11│HK1L12│HK2L12│
├─────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ Toán    │ 8.5  │ 8.7* │ 9.0  │ 9.2* │  -   │  -   │
│ Vật lý  │ 7.2  │ 7.5* │ 8.0  │  -   │  -   │  -   │
│ ...     │ ...  │ ...  │ ...  │ ...  │ ...  │ ...  │
└─────────┴──────┴──────┴──────┴──────┴──────┴──────┘

Chú thích:
  Số đen: Điểm thực tế (actual)
  Số xanh*: Điểm dự đoán (predicted)
  -: Chưa có dữ liệu
```

**Thống kê:**
- GPA tổng thể
- GPA theo từng học kỳ
- Điểm trung bình từng môn
- Tổng số điểm đã nhập / tổng

#### 2.2.2. Nhập điểm mới

**Phương pháp 1: Nhập trực tiếp**

1. Click vào ô trống hoặc ô có điểm
2. Modal hiển thị:
   ```
   ┌──────────────────────────┐
   │ Cập nhật điểm            │
   ├──────────────────────────┤
   │ Môn: Toán                │
   │ Học kỳ: 1                │
   │ Lớp: 10                  │
   │                          │
   │ Điểm: [____]             │
   │       (0.0 - 10.0)       │
   │                          │
   │ [Hủy]      [Lưu]        │
   └──────────────────────────┘
   ```
3. Nhập điểm (0-10, cho phép thập phân)
4. Click "Lưu"
5. Hệ thống:
   - Lưu điểm vào database
   - Tự động chạy ML prediction
   - Cập nhật UI real-time

**Phương pháp 2: Nhập qua Chatbot**

1. Mở chatbot
2. Gõ: "Điểm toán học kỳ 1 lớp 10 của tôi là 8.5"
3. Bot trả lời: "Tôi hiểu bạn muốn cập nhật điểm Toán HK1 L10 thành 8.5. Xác nhận?"
4. Gõ: "Đúng" hoặc "OK"
5. Bot: "Đã cập nhật!"

**Phương pháp 3: Import Excel (Developer only)**

Xem mục 2.7

#### 2.2.3. Xóa điểm

1. Click vào ô có điểm
2. Trong modal, click nút "Xóa"
3. Xác nhận xóa
4. Điểm bị xóa, prediction tự động cập nhật

---

### 2.3. Chatbot AI

#### 2.3.1. Tạo cuộc trò chuyện mới

**Truy cập:** Menu → "Chatbot" hoặc `/chat`

**Tạo session:**
- Click nút "+" (New Chat)
- Session mới được tạo với title mặc định
- Có thể đổi tên session sau

**Quản lý sessions:**
```
Sidebar (Left):
├─ 📝 Hỏi về điểm toán (2 giờ trước)
├─ 📝 Tư vấn học tập (hôm qua)
└─ 📝 Cập nhật thông tin (3 ngày trước)

Actions:
- Click vào session → Switch
- Hover → Hiện nút Delete
- Delete → Xóa toàn bộ lịch sử chat
```

#### 2.3.2. Trò chuyện với Bot

**Input box:**
```
┌────────────────────────────────────────┐
│ Nhập tin nhắn...                       │
│                                        │
│                              [📎] [📤] │
└────────────────────────────────────────┘
```

**Các loại câu hỏi hỗ trợ:**

**1. Hỏi về điểm số**
```
User: "Điểm toán của tôi như thế nào?"
Bot:  "Bạn có điểm Toán:
       - HK1 L10: 8.5
       - HK2 L10: 8.7 (dự đoán)
       - HK1 L11: 9.0
       Điểm trung bình môn Toán: 8.73"
```

**2. Cập nhật điểm**
```
User: "Điểm lý học kỳ 2 lớp 10 của tôi là 7.5"
Bot:  "Tôi hiểu bạn muốn cập nhật điểm Vật lý 
       HK2 L10 thành 7.5. Xác nhận?"
User: "Đúng"
Bot:  "✓ Đã cập nhật điểm Vật lý HK2 L10 = 7.5"
```

**3. Hỏi dự đoán**
```
User: "Dự đoán điểm toán học kỳ 2 của tôi?"
Bot:  "Dựa trên điểm hiện tại, dự đoán điểm 
       Toán HK2 L10 của bạn là 8.7.
       Điểm này cao hơn trung bình dataset (8.2)"
```

**4. Tư vấn học tập**
```
User: "Làm thế nào để cải thiện điểm hóa?"
Bot:  "Để cải thiện điểm Hóa học:
       1. Ôn lại lý thuyết cơ bản
       2. Làm bài tập phương trình hóa học
       3. Thực hành thí nghiệm
       4. Học nhóm với bạn bè
       
       Điểm Hóa hiện tại: 7.0
       Mục tiêu đề xuất: 7.5-8.0"
```

**5. Cập nhật profile**
```
User: "Email của tôi là student@example.com"
Bot:  "Bạn muốn cập nhật email thành 
       student@example.com?"
User: "OK"
Bot:  "✓ Đã cập nhật email"
```

**6. So sánh với benchmark**
```
User: "So sánh điểm của tôi với trung bình"
Bot:  "So sánh với dataset:
       - GPA của bạn: 8.2
       - Trung bình dataset: 7.5
       - Bạn đang ở top 25%
       
       Môn xuất sắc: Toán (9.0 vs 7.8)
       Môn cần cải thiện: Lịch sử (6.5 vs 7.0)"
```

#### 2.3.3. Xem pending confirmations

**Khi có update chờ xác nhận:**
```
┌────────────────────────────────────┐
│ ⚠️ Có 1 thay đổi chờ xác nhận      │
├────────────────────────────────────┤
│ Cập nhật điểm Toán HK1 L10: 8.5   │
│                                    │
│ [Hủy]              [Xác nhận]     │
└────────────────────────────────────┘
```

**Actions:**
- Xác nhận: Apply changes
- Hủy: Discard changes
- Timeout: Auto-cancel sau 1 giờ

#### 2.3.4. Chat features

**Markdown support:**
- **Bold**, *Italic*
- Lists, Tables
- Code blocks
- Links

**Real-time indicators:**
```
Bot đang nhập...  [💬 ...]
```

**Message metadata:**
- Timestamp
- Message ID
- Role (user/assistant)

---

### 2.4. Data Visualization

#### 2.4.1. Dashboard Overview

**Truy cập:** Menu → "Biểu đồ" hoặc `/data`

**Layout:**
```
┌────────────────────────────────────────────────┐
│  TỔNG QUAN HỌC TẬP                             │
├────────────┬───────────────────────────────────┤
│ GPA: 8.2   │  Xu hướng: ↗️ +0.3               │
│ Ranking: Top 25%                               │
└────────────┴───────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  BIỂU ĐỒ XU HƯỚNG ĐIỂM                        │
│  [Line Chart]                                  │
│   ^                                            │
│ 10│              •                             │
│  9│        •   •   •                           │
│  8│    •       •                               │
│  7│                                            │
│   └────────────────────────────→               │
│    HK1  HK2  HK1  HK2  HK1  HK2               │
│    L10  L10  L11  L11  L12  L12               │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  SO SÁNH THEO MÔN HỌC                         │
│  [Bar Chart]                                   │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  PHÂN TÍCH ĐA CHIỀU                           │
│  [Radar Chart]                                 │
└────────────────────────────────────────────────┘
```

#### 2.4.2. Line Chart - Xu hướng theo thời gian

**Chức năng:**
- Hiển thị điểm qua các học kỳ
- 2 đường: Actual (green) & Predicted (blue)
- Hover để xem chi tiết từng điểm

**Filters:**
```
Môn học: [Tất cả ▼]
         Toán
         Vật lý
         ...

Loại điểm: [x] Actual  [x] Predicted

Khối: [x] 10  [x] 11  [x] 12
```

**Tương tác:**
- Click legend để ẩn/hiện series
- Zoom: Scroll wheel
- Pan: Click & drag

#### 2.4.3. Bar Chart - So sánh môn học

**Hiển thị:**
- Mỗi môn: 2 cột (Actual vs Predicted)
- Sort theo điểm cao → thấp
- Color-coded by performance level

**Legend:**
```
■ Xuất sắc (9.0-10)   Green
■ Giỏi (8.0-8.9)      Blue
■ Khá (6.5-7.9)       Yellow
■ Trung bình (5.0-6.4) Orange
■ Yếu (<5.0)          Red
```

#### 2.4.4. Radar Chart - Phân tích năng lực

**Trục:**
- 9 trục = 9 môn học
- Giá trị: 0-10
- Vùng tô: Actual scores
- Đường nét đứt: Predicted

**Use case:**
- Nhìn tổng quan năng lực
- Xác định điểm mạnh/yếu
- So sánh cân bằng môn học

#### 2.4.5. Statistics Panel

```
┌─────────────────────────────────────┐
│ THỐNG KÊ CHI TIẾT                   │
├─────────────────────────────────────┤
│ Tổng số điểm: 24/54 (44%)          │
│ Điểm thực tế: 18                    │
│ Điểm dự đoán: 6                     │
│                                     │
│ GPA hiện tại: 8.2                   │
│ GPA dự kiến TN: 8.5                 │
│                                     │
│ Môn cao nhất: Toán (9.0)           │
│ Môn thấp nhất: Lịch sử (6.5)       │
│                                     │
│ Cải thiện: +0.3 từ HK trước        │
└─────────────────────────────────────┘
```

---

### 2.5. Learning Goals (Mục tiêu học tập)

#### 2.5.1. Xem danh sách mục tiêu

**Truy cập:** Menu → "Mục tiêu" hoặc `/goals`

**Giao diện:**
```
┌────────────────────────────────────────────────┐
│  MỤC TIÊU HỌC TẬP                   [+ Thêm]  │
├────────────────────────────────────────────────┤
│ 🎯 Đạt điểm 9.0 môn Toán HK2                  │
│    Deadline: 15/12/2025                        │
│    Priority: High                              │
│    Status: In Progress                         │
│    [✏️ Edit] [🗑️ Delete]                       │
├────────────────────────────────────────────────┤
│ 🎯 Cải thiện điểm Hóa lên 8.0                 │
│    Deadline: 20/12/2025                        │
│    Priority: Medium                            │
│    Status: Not Started                         │
│    [✏️ Edit] [🗑️ Delete]                       │
└────────────────────────────────────────────────┘
```

#### 2.5.2. Tạo mục tiêu mới

**Click "+" → Form:**
```
┌────────────────────────────────────┐
│ THÊM MỤC TIÊU MỚI                  │
├────────────────────────────────────┤
│ Tiêu đề:                           │
│ [_______________________________]  │
│                                    │
│ Mô tả:                             │
│ [_______________________________]  │
│ [_______________________________]  │
│                                    │
│ Ngày đích: [📅 15/12/2025]        │
│                                    │
│ Độ ưu tiên:                        │
│ ○ Low  ● Medium  ○ High           │
│                                    │
│ Trạng thái:                        │
│ ● Not Started  ○ In Progress       │
│ ○ Completed                        │
│                                    │
│ [Hủy]              [Lưu]          │
└────────────────────────────────────┘
```

#### 2.5.3. Cập nhật tiến độ

1. Click "Edit" trên mục tiêu
2. Thay đổi status:
   - Not Started → In Progress
   - In Progress → Completed
3. Thêm notes (optional)
4. Save

**Completed goals:**
```
✅ Đạt điểm 9.0 môn Toán HK2
   Hoàn thành: 10/12/2025
   Kết quả: 9.2 ⭐
```

---

### 2.6. Settings (Cài đặt)

#### 2.6.1. Profile Settings

**Truy cập:** Avatar → "Cài đặt" hoặc `/settings`

**Tab: Thông tin cá nhân**
```
┌────────────────────────────────────┐
│ THÔNG TIN CÁ NHÂN                  │
├────────────────────────────────────┤
│ Tên: [Nguyễn Văn]                 │
│ Họ: [A]                            │
│ Email: [student@example.com]       │
│ Điện thoại: [0123456789]           │
│ Tuổi: [16]                         │
│ Khối: [x] 10  [ ] 11  [ ] 12      │
│                                    │
│ [Hủy]              [Lưu]          │
└────────────────────────────────────┘
```

#### 2.6.2. Preferences

**Tab: Tùy chọn**
```
┌────────────────────────────────────┐
│ PREFERENCES                         │
├────────────────────────────────────┤
│ Ngôn ngữ:                          │
│ [Tiếng Việt ▼]                     │
│                                    │
│ Theme:                             │
│ ○ Light  ● Auto  ○ Dark           │
│                                    │
│ Notifications:                     │
│ [x] Score updates                  │
│ [x] New predictions                │
│ [x] Chat messages                  │
│ [ ] Weekly reports                 │
│                                    │
│ Learning preferences:              │
│ Phong cách học: [Trực quan ▼]     │
│ Môn yêu thích: [Toán, Lý]         │
│                                    │
│ [Lưu thay đổi]                     │
└────────────────────────────────────┘
```

#### 2.6.3. Security

**Tab: Bảo mật**
```
┌────────────────────────────────────┐
│ THAY ĐỔI MẬT KHẨU                  │
├────────────────────────────────────┤
│ Mật khẩu hiện tại:                 │
│ [••••••••]                         │
│                                    │
│ Mật khẩu mới:                      │
│ [••••••••]                         │
│                                    │
│ Xác nhận mật khẩu:                 │
│ [••••••••]                         │
│                                    │
│ [Thay đổi mật khẩu]               │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│ PHIÊN ĐĂNG NHẬP                    │
├────────────────────────────────────┤
│ • Windows - Chrome (Đang dùng)     │
│   IP: 192.168.1.100                │
│   Last active: Vừa xong            │
│                                    │
│ [Đăng xuất tất cả thiết bị khác]  │
└────────────────────────────────────┘
```

---

### 2.7. Developer Dashboard

**⚠️ Chỉ dành cho Developer/Admin role**

#### 2.7.1. Dataset Management

**Upload Excel:**
```
┌────────────────────────────────────┐
│ UPLOAD DATASET                     │
├────────────────────────────────────┤
│ File format: .xlsx, .xls           │
│                                    │
│ [📁 Choose File]                   │
│ > student_scores.xlsx              │
│                                    │
│ Expected columns:                  │
│ - Toan_1_10, Toan_2_10, ...       │
│ - Each row = 1 student sample     │
│                                    │
│ [Upload & Import]                  │
└────────────────────────────────────┘
```

**Dataset Summary:**
```
┌────────────────────────────────────┐
│ DATASET STATISTICS                 │
├────────────────────────────────────┤
│ Total samples: 500                 │
│ Total features: 54                 │
│ Complete records: 450 (90%)        │
│                                    │
│ Score distribution:                │
│ Mean: 7.5                          │
│ Median: 7.8                        │
│ Std: 1.2                           │
│                                    │
│ By subject:                        │
│ Toán: 7.8 ± 1.1                    │
│ Vật lý: 7.2 ± 1.3                  │
│ ...                                │
│                                    │
│ [View Full Analysis]               │
└────────────────────────────────────┘
```

#### 2.7.2. Model Configuration

**Model Selection:**
```
┌────────────────────────────────────┐
│ ACTIVE MODEL                       │
├────────────────────────────────────┤
│ Current: K-Nearest Neighbors (KNN) │
│ Version: 5                         │
│ Updated: 2025-11-30 10:30         │
│                                    │
│ Change to:                         │
│ ○ K-Nearest Neighbors (KNN)       │
│ ○ Kernel Regression               │
│ ○ LWLR (Locally Weighted LR)      │
│                                    │
│ [Apply Changes]                    │
│ ⚠️ Will recalculate all predictions│
└────────────────────────────────────┘
```

**Parameter Tuning:**
```
┌────────────────────────────────────┐
│ MODEL PARAMETERS                   │
├────────────────────────────────────┤
│ KNN:                               │
│ n_neighbors: [====|====] 15        │
│              5    10   15   20     │
│                                    │
│ Kernel Regression:                 │
│ bandwidth: [=====|===] 1.25        │
│           0.5   1.0   1.5   2.0    │
│                                    │
│ LWLR:                              │
│ tau: [======|==] 3.0               │
│     1.0   2.0   3.0   4.0   5.0    │
│                                    │
│ [Save Parameters]                  │
│ [Reset to Defaults]                │
└────────────────────────────────────┘
```

#### 2.7.3. Model Evaluation

**Run Evaluation:**
```
┌────────────────────────────────────────────────┐
│ MODEL EVALUATION RESULTS                       │
├────────────────────────────────────────────────┤
│ Task 1: Predict Grade 12 from Grades 10-11   │
├──────────┬──────┬──────┬──────┬────────┬──────┤
│ Model    │ MAE  │ RMSE │Acc@0.5│ Acc@1.0│ Time │
├──────────┼──────┼──────┼──────┼────────┼──────┤
│ KNN      │ 0.45 │ 0.62 │ 78%  │  94%   │ 0.2s │
│ Kernel   │ 0.52 │ 0.68 │ 72%  │  91%   │ 0.8s │
│ LWLR     │ 0.48 │ 0.65 │ 75%  │  93%   │ 1.5s │
└──────────┴──────┴──────┴──────┴────────┴──────┘

Task 2: Predict Grade 11 from Grade 10
├──────────┬──────┬──────┬──────┬────────┬──────┤
│ Model    │ MAE  │ RMSE │Acc@0.5│ Acc@1.0│ Time │
├──────────┼──────┼──────┼──────┼────────┼──────┤
│ KNN      │ 0.38 │ 0.51 │ 82%  │  96%   │ 0.2s │
│ Kernel   │ 0.44 │ 0.58 │ 76%  │  93%   │ 0.7s │
│ LWLR     │ 0.41 │ 0.55 │ 79%  │  95%   │ 1.3s │
└──────────┴──────┴──────┴──────┴────────┴──────┘

🏆 Best Model: KNN
   - Lowest MAE across both tasks
   - Highest accuracy @ 0.5 threshold
   - Fastest inference time

💡 Recommendation: Keep using KNN with n=15
```

#### 2.7.4. Pipeline Management

**Manual Trigger:**
```
┌────────────────────────────────────┐
│ ML PIPELINE CONTROL                │
├────────────────────────────────────┤
│ Last run: 2025-11-30 09:15        │
│ Status: Completed                  │
│ Processed: 50 users                │
│ Duration: 2.3s                     │
│                                    │
│ [Run Pipeline Now]                 │
│ ⚠️ This will:                      │
│ - Recalculate all predictions     │
│ - Update all users                │
│ - May take several seconds        │
│                                    │
│ Auto-run triggers:                 │
│ [x] After dataset upload           │
│ [x] After model change             │
│ [x] After parameter update         │
└────────────────────────────────────┘
```

**Progress Tracking:**
```
Pipeline running...
████████████████░░░░  80% (40/50 users)
Estimated time remaining: 5s
```

---

### 2.8. Notifications

#### 2.8.1. Notification Bell

**Location:** Top-right header

**Badge:** Shows unread count
```
🔔 (3)  ← 3 unread notifications
```

**Click to open dropdown:**
```
┌────────────────────────────────────┐
│ THÔNG BÁO                    [⚙️]  │
├────────────────────────────────────┤
│ • Điểm Toán đã được cập nhật       │
│   2 phút trước                     │
│                                    │
│ • Có dự đoán mới cho 6 môn học    │
│   10 phút trước                    │
│                                    │
│ • ML model changed to Kernel       │
│   1 giờ trước                      │
│                                    │
│ [Xem tất cả]  [Đánh dấu đã đọc]   │
└────────────────────────────────────┘
```

#### 2.8.2. Real-time Updates

**Types:**
1. **Score Update**
   - Icon: 📊
   - "Điểm [Môn] đã được cập nhật"

2. **Prediction Update**
   - Icon: 🔮
   - "Có [N] dự đoán mới"

3. **System**
   - Icon: ⚙️
   - "Model đã thay đổi"
   - "Dataset đã cập nhật"

4. **Chat**
   - Icon: 💬
   - "Bot đã trả lời tin nhắn"

**Actions:**
- Click notification → Navigate to related page
- Swipe left → Delete
- Settings → Configure notification types

---

## 3. SCREENSHOTS MÔ PHỎNG

### 3.1. Login & Authentication

**Màn hình đăng nhập:**
```
╔══════════════════════════════════════════════════════════╗
║                    🎓 EDUTWIN                            ║
║            Hệ thống Hỗ trợ Học tập Thông minh           ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║    ┌────────────────────────────────────────────┐      ║
║    │ 👤 ĐĂNG NHẬP                               │      ║
║    ├────────────────────────────────────────────┤      ║
║    │                                            │      ║
║    │  Username                                  │      ║
║    │  ┌──────────────────────────────────────┐ │      ║
║    │  │ student123                            │ │      ║
║    │  └──────────────────────────────────────┘ │      ║
║    │                                            │      ║
║    │  Password                                  │      ║
║    │  ┌──────────────────────────────────────┐ │      ║
║    │  │ ••••••••••                            │ │      ║
║    │  └──────────────────────────────────────┘ │      ║
║    │                                            │      ║
║    │  ☐ Ghi nhớ đăng nhập                      │      ║
║    │                                            │      ║
║    │     ┌──────────────────────────┐          │      ║
║    │     │    ĐĂNG NHẬP             │          │      ║
║    │     └──────────────────────────┘          │      ║
║    │                                            │      ║
║    │  Chưa có tài khoản? [Đăng ký ngay]       │      ║
║    └────────────────────────────────────────────┘      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

**First Login - Onboarding:**
```
╔══════════════════════════════════════════════════════════╗
║  CHÀO MỪNG ĐẾN VỚI EDUTWIN! 🎉                          ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  [●]━━━━━[○]━━━━━[○]                                   ║
║   Bước 1   Bước 2   Bước 3                              ║
║                                                          ║
║  ┌────────────────────────────────────────────────┐    ║
║  │ THÔNG TIN CÁ NHÂN                              │    ║
║  ├────────────────────────────────────────────────┤    ║
║  │                                                │    ║
║  │  Họ:      ┌──────────────────┐                │    ║
║  │           │ Nguyễn           │                │    ║
║  │           └──────────────────┘                │    ║
║  │                                                │    ║
║  │  Tên:     ┌──────────────────┐                │    ║
║  │           │ Văn A            │                │    ║
║  │           └──────────────────┘                │    ║
║  │                                                │    ║
║  │  Email:   ┌──────────────────┐                │    ║
║  │           │ student@email.com│                │    ║
║  │           └──────────────────┘                │    ║
║  │                                                │    ║
║  │  Khối học hiện tại: *                         │    ║
║  │  ○ Lớp 10  ●Lớp 11  ○ Lớp 12               │    ║
║  │                                                │    ║
║  │        [Bỏ qua]    [Tiếp tục →]              │    ║
║  └────────────────────────────────────────────────┘    ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

---

### 3.2. Dashboard - Trang chủ

```
╔══════════════════════════════════════════════════════════════════════╗
║ 🎓 EduTwin  [Chatbot] [Biểu đồ] [Điểm số] [Mục tiêu]    🔔(2) [👤] ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  TỔNG QUAN HỌC TẬP                         Xin chào, Nguyễn Văn A! ║
║  ┌──────────────┬──────────────┬──────────────┬──────────────┐     ║
║  │   📊 GPA     │  📈 Xu hướng │  🎯 Hoàn tất │  🔮 Dự đoán │     ║
║  │              │              │              │              │     ║
║  │    8.2       │   ↗️ +0.3    │   24/54      │      6       │     ║
║  │  Giỏi        │   Tốt lên    │    44%       │   điểm mới   │     ║
║  └──────────────┴──────────────┴──────────────┴──────────────┘     ║
║                                                                      ║
║  BIỂU ĐỒ XU HƯỚNG ĐIỂM                    [Toán ▼] [Tất cả khối]  ║
║  ┌────────────────────────────────────────────────────────────┐    ║
║  │ 10 │                                           •           │    ║
║  │  9 │                    •           •                      │    ║
║  │  8 │         •    •  •       •                            │    ║
║  │  7 │                                                       │    ║
║  │  6 │                                                       │    ║
║  │    └──────────────────────────────────────────────────────│    ║
║  │      HK1  HK2  HK1  HK2  HK1  HK2  TN                    │    ║
║  │      L10  L10  L11  L11  L12  L12  L12                   │    ║
║  │                                                            │    ║
║  │      ━━ Điểm thực tế    ━ ━ Điểm dự đoán                │    ║
║  └────────────────────────────────────────────────────────────┘    ║
║                                                                      ║
║  ĐIỂM NỔI BẬT                           MỤC TIÊU GẦN NHẤT          ║
║  ┌────────────────────────────┐  ┌──────────────────────────────┐ ║
║  │ ⭐ Môn cao nhất: Toán      │  │ 🎯 Đạt 9.0 môn Toán HK2     │ ║
║  │    Điểm: 9.0               │  │    Deadline: 15/12/2025      │ ║
║  │                            │  │    Progress: 85%             │ ║
║  │ 📉 Cần cải thiện: Lịch sử │  │                              │ ║
║  │    Điểm: 6.5               │  │ [Xem tất cả mục tiêu →]     │ ║
║  └────────────────────────────┘  └──────────────────────────────┘ ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

### 3.3. Chatbot Interface

```
╔═══════════════════════════════════════════════════════════════════╗
║ 🎓 EduTwin › Chatbot                                   🔔 [👤]    ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║ ┌──────────┬────────────────────────────────────────────────────┐║
║ │Sessions  │ Chat: Tư vấn học tập                         [⋮]  │║
║ ├──────────┼────────────────────────────────────────────────────┤║
║ │[+ New]   │                                                    │║
║ │          │ ┌────────────────────────────────────────────┐    │║
║ │📝 Tư vấn │ │ 👤 Điểm toán của tôi như thế nào?         │    │║
║ │  học tập │ │    10:15 AM                                │    │║
║ │ 2h trước │ └────────────────────────────────────────────┘    │║
║ │          │                                                    │║
║ │📝 Hỏi về │ ┌────────────────────────────────────────────┐    │║
║ │  điểm    │ │ 🤖 Bạn có điểm Toán:                      │    │║
║ │ Hôm qua  │ │    • HK1 L10: 8.5                          │    │║
║ │          │ │    • HK2 L10: 8.7 (dự đoán)               │    │║
║ │📝 Cập    │ │    • HK1 L11: 9.0                          │    │║
║ │  nhật    │ │    Điểm TB môn Toán: 8.73/10              │    │║
║ │ 3 ngày   │ │    Xếp loại: Giỏi ⭐                       │    │║
║ │          │ │    10:15 AM                                │    │║
║ │          │ └────────────────────────────────────────────┘    │║
║ │          │                                                    │║
║ │          │ ┌────────────────────────────────────────────┐    │║
║ │          │ │ 👤 Làm sao để cải thiện điểm hóa?         │    │║
║ │          │ │    10:17 AM                                │    │║
║ │          │ └────────────────────────────────────────────┘    │║
║ │          │                                                    │║
║ │          │ ┌────────────────────────────────────────────┐    │║
║ │          │ │ 🤖 Bot đang nhập...                       │    │║
║ │          │ └────────────────────────────────────────────┘    │║
║ │          │                                                    │║
║ │          │                                                    │║
║ │          ├────────────────────────────────────────────────────┤║
║ │          │ Nhập tin nhắn...                        📎  📤   │║
║ └──────────┴────────────────────────────────────────────────────┘║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

**Chatbot - Pending Confirmation:**
```
╔═══════════════════════════════════════════════════════════╗
║ Chat với Bot                                              ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║ ┌───────────────────────────────────────────────────┐    ║
║ │ 👤 Điểm lý học kỳ 2 lớp 10 của tôi là 7.5        │    ║
║ └───────────────────────────────────────────────────┘    ║
║                                                           ║
║ ┌───────────────────────────────────────────────────┐    ║
║ │ 🤖 Tôi hiểu bạn muốn cập nhật:                   │    ║
║ │                                                   │    ║
║ │    📊 Môn: Vật lý                                │    ║
║ │    📅 Học kỳ: 2                                  │    ║
║ │    🎓 Lớp: 10                                    │    ║
║ │    ✏️  Điểm: 7.5                                 │    ║
║ │                                                   │    ║
║ │    Xác nhận cập nhật không?                      │    ║
║ │                                                   │    ║
║ │    ╔═══════════════════════════════════════╗    │    ║
║ │    ║ ⚠️  THAY ĐỔI CHỜ XÁC NHẬN            ║    │    ║
║ │    ╟───────────────────────────────────────╢    │    ║
║ │    ║ Cập nhật Vật lý HK2 L10: 7.5         ║    │    ║
║ │    ║                                       ║    │    ║
║ │    ║  [❌ Hủy]         [✅ Xác nhận]      ║    │    ║
║ │    ╚═══════════════════════════════════════╝    │    ║
║ └───────────────────────────────────────────────────┘    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```

---

### 3.4. Study Scores Management

**Bảng điểm:**
```
╔═══════════════════════════════════════════════════════════════════════════╗
║ QUẢN LÝ ĐIỂM SỐ                                        GPA: 8.2  Khá      ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║ ┌───────────┬────────┬────────┬────────┬────────┬────────┬────────┬────┐║
║ │ Môn học   │ HK1 L10│ HK2 L10│ HK1 L11│ HK2 L11│ HK1 L12│ HK2 L12│ TN │║
║ ├───────────┼────────┼────────┼────────┼────────┼────────┼────────┼────┤║
║ │ Toán      │  8.5   │  8.7*  │  9.0   │  9.2*  │   -    │   -    │ -  │║
║ │           │   ✓    │   🔮   │   ✓    │   🔮   │        │        │    │║
║ ├───────────┼────────┼────────┼────────┼────────┼────────┼────────┼────┤║
║ │ Ngữ văn   │  7.8   │  8.0   │  8.2   │  8.4*  │   -    │   -    │ -  │║
║ │           │   ✓    │   ✓    │   ✓    │   🔮   │        │        │    │║
║ ├───────────┼────────┼────────┼────────┼────────┼────────┼────────┼────┤║
║ │ Vật lý    │  7.2   │  7.5*  │  8.0   │   -    │   -    │   -    │ -  │║
║ │           │   ✓    │   🔮   │   ✓    │        │        │        │    │║
║ ├───────────┼────────┼────────┼────────┼────────┼────────┼────────┼────┤║
║ │ Hóa học   │  7.0   │  7.2*  │  7.5   │   -    │   -    │   -    │ -  │║
║ │           │   ✓    │   🔮   │   ✓    │        │        │        │    │║
║ └───────────┴────────┴────────┴────────┴────────┴────────┴────────┴────┘║
║                                                                           ║
║ Chú thích:  ✓ = Đã nhập    🔮 = Dự đoán    * = Giá trị dự đoán          ║
║                                                                           ║
║ ┌─────────────────────────────────────────────────────────────────────┐ ║
║ │ THỐNG KÊ                                                            │ ║
║ ├─────────────────────────────────────────────────────────────────────┤ ║
║ │ Tổng số điểm đã nhập: 18/54 (33%)                                  │ ║
║ │ Điểm dự đoán: 6 môn                                                │ ║
║ │ GPA học kỳ 1 lớp 11: 8.18                                          │ ║
║ │ Dự đoán GPA tốt nghiệp: 8.5                                        │ ║
║ └─────────────────────────────────────────────────────────────────────┘ ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

**Modal cập nhật điểm:**
```
        ╔═══════════════════════════════╗
        ║  CẬP NHẬT ĐIỂM                ║
        ╟───────────────────────────────╢
        ║                               ║
        ║  Môn học:     Toán            ║
        ║  Học kỳ:      1               ║
        ║  Lớp:         10              ║
        ║                               ║
        ║  Điểm số: ┌────────┐          ║
        ║           │  8.5   │          ║
        ║           └────────┘          ║
        ║           (0.0 - 10.0)        ║
        ║                               ║
        ║  Ghi chú (tùy chọn):          ║
        ║  ┌─────────────────────────┐  ║
        ║  │ Điểm kiểm tra 15 phút   │  ║
        ║  └─────────────────────────┘  ║
        ║                               ║
        ║  [Xóa điểm]                   ║
        ║                               ║
        ║  ┌──────┐       ┌──────────┐  ║
        ║  │ Hủy  │       │   Lưu    │  ║
        ║  └──────┘       └──────────┘  ║
        ║                               ║
        ╚═══════════════════════════════╝
```

---

### 3.5. Data Visualization

**Dashboard biểu đồ:**
```
╔═══════════════════════════════════════════════════════════════════════╗
║ PHÂN TÍCH HỌC TẬP                                    [Xuất PDF] [⚙️] ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║ BIỂU ĐỒ XU HƯỚNG                         Filter: [Toán ▼] [L10-12] ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ 10 │                                              •            │   ║
║ │ 9  │                       •          •                       │   ║
║ │ 8  │          •      •  •       •                            │   ║
║ │ 7  │                                                          │   ║
║ │ 6  │                                                          │   ║
║ │    └──────────────────────────────────────────────────────── │   ║
║ │     HK1   HK2   HK1   HK2   HK1   HK2   TN                  │   ║
║ │     L10   L10   L11   L11   L12   L12   L12                 │   ║
║ │                                                               │   ║
║ │     ━━━ Điểm thực tế (8.5)    ━ ━ ━ Dự đoán (8.7)         │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
║ SO SÁNH CÁC MÔN                          RADAR CHART                ║
║ ┌────────────────────────┐   ┌──────────────────────────────────┐  ║
║ │     Toán    ████████   │   │           Toán                   │  ║
║ │             ████████ 9.0│   │             •                    │  ║
║ │                        │   │        Anh•   •Văn               │  ║
║ │     Lý      ██████     │   │            •                     │  ║
║ │             ██████ 7.5 │   │       Sử•       •Địa             │  ║
║ │                        │   │          •   •                   │  ║
║ │     Hóa     █████      │   │         Lý•Hóa                   │  ║
║ │             █████ 7.0  │   │            •                     │  ║
║ │                        │   │           Sinh                   │  ║
║ │ ■ Actual  ■ Predicted  │   │                                  │  ║
║ └────────────────────────┘   └──────────────────────────────────┘  ║
║                                                                       ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ INSIGHTS & RECOMMENDATIONS                                    │   ║
║ ├───────────────────────────────────────────────────────────────┤   ║
║ │ 💡 Điểm Toán của bạn cao hơn 15% so với trung bình dataset   │   ║
║ │ 📈 Xu hướng tăng +0.3 điểm/học kỳ - Tiếp tục phát huy!       │   ║
║ │ ⚠️  Hóa học cần chú ý - thấp hơn mục tiêu 0.5 điểm            │   ║
║ │ 🎯 Với tiến độ hiện tại, dự đoán GPA TN: 8.5                 │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

### 3.6. Developer Dashboard

**Dataset Management:**
```
╔═══════════════════════════════════════════════════════════════════════╗
║ DEVELOPER DASHBOARD                                        [Admin] 👤 ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║ DATASET MANAGEMENT                                                    ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ UPLOAD NEW DATASET                                            │   ║
║ │                                                               │   ║
║ │ ┌─────────────────────────────────────────────────────────┐  │   ║
║ │ │ 📁 Drag & Drop Excel file here                          │  │   ║
║ │ │    or [Browse Files]                                    │  │   ║
║ │ │                                                          │  │   ║
║ │ │    Supported: .xlsx, .xls                               │  │   ║
║ │ └─────────────────────────────────────────────────────────┘  │   ║
║ │                                                               │   ║
║ │ Selected: student_scores_2025.xlsx (250 KB)                  │   ║
║ │                                                               │   ║
║ │ [Upload & Import]                                             │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
║ CURRENT DATASET STATISTICS                                            ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ Total samples: 500                      Last update: Today    │   ║
║ │ Complete records: 450 (90%)             Source: Admin upload  │   ║
║ │                                                               │   ║
║ │ Score Distribution:                                           │   ║
║ │ ├─ Mean: 7.5                                                 │   ║
║ │ ├─ Median: 7.8                                               │   ║
║ │ ├─ Std Dev: 1.2                                              │   ║
║ │ ├─ Min: 3.0                                                  │   ║
║ │ └─ Max: 10.0                                                 │   ║
║ │                                                               │   ║
║ │ By Subject:                                                   │   ║
║ │   Toán:    7.8 ± 1.1    [████████████░░░░] 75%              │   ║
║ │   Vật lý:  7.2 ± 1.3    [██████████░░░░░░] 65%              │   ║
║ │   Hóa:     7.0 ± 1.4    [█████████░░░░░░░] 62%              │   ║
║ │                                                               │   ║
║ │ [View Full Analysis] [Export Stats]                          │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

**Model Configuration:**
```
╔═══════════════════════════════════════════════════════════════════════╗
║ MODEL CONFIGURATION                                                   ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║ ACTIVE MODEL                                                          ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ Current Model: K-Nearest Neighbors (KNN)                      │   ║
║ │ Version: 5                                                    │   ║
║ │ Last updated: 2025-11-30 10:30 by admin                      │   ║
║ │                                                               │   ║
║ │ Select Model:                                                 │   ║
║ │ ● K-Nearest Neighbors (KNN)        - Fastest, good accuracy  │   ║
║ │ ○ Kernel Regression                - Smooth predictions      │   ║
║ │ ○ LWLR (Locally Weighted LR)       - Best for trends         │   ║
║ │                                                               │   ║
║ │ [Apply Model Change]  ⚠️ Will trigger full recalculation     │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
║ MODEL PARAMETERS                                                      ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ KNN Parameters:                                               │   ║
║ │   n_neighbors (k): [━━━━━●━━━━━] 15                         │   ║
║ │                     5    10   15   20   25                    │   ║
║ │   Current: 15  |  Recommended: 10-20                         │   ║
║ │                                                               │   ║
║ │ Kernel Regression Parameters:                                 │   ║
║ │   bandwidth (σ): [━━━━━●━━━━━] 1.25                         │   ║
║ │                   0.5  1.0  1.5  2.0  2.5                     │   ║
║ │   Current: 1.25  |  Recommended: 1.0-2.0                     │   ║
║ │                                                               │   ║
║ │ LWLR Parameters:                                              │   ║
║ │   tau (τ): [━━━━━━●━━━━] 3.0                                │   ║
║ │            1.0  2.0  3.0  4.0  5.0                            │   ║
║ │   Current: 3.0  |  Recommended: 2.0-4.0                      │   ║
║ │                                                               │   ║
║ │ [Save Parameters] [Reset to Defaults]                        │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

**Model Evaluation Results:**
```
╔═══════════════════════════════════════════════════════════════════════╗
║ MODEL EVALUATION RESULTS                          [Run Evaluation]   ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║ Task 1: Predict Grade 12 from Grades 10-11                          ║
║ ┌────────────┬──────┬──────┬──────┬────────┬────────┬──────────┐   ║
║ │ Model      │ MAE  │ RMSE │ R²   │Acc@0.5 │ Acc@1.0│ Time(s)  │   ║
║ ├────────────┼──────┼──────┼──────┼────────┼────────┼──────────┤   ║
║ │ KNN        │ 0.45 │ 0.62 │ 0.85 │  78%   │  94%   │   0.2    │   ║
║ │            │  🏆  │  🏆  │  🏆  │   🏆   │   🏆   │    🏆    │   ║
║ ├────────────┼──────┼──────┼──────┼────────┼────────┼──────────┤   ║
║ │ Kernel Reg │ 0.52 │ 0.68 │ 0.81 │  72%   │  91%   │   0.8    │   ║
║ ├────────────┼──────┼──────┼──────┼────────┼────────┼──────────┤   ║
║ │ LWLR       │ 0.48 │ 0.65 │ 0.83 │  75%   │  93%   │   1.5    │   ║
║ └────────────┴──────┴──────┴──────┴────────┴────────┴──────────┘   ║
║                                                                       ║
║ Task 2: Predict Grade 11 from Grade 10                              ║
║ ┌────────────┬──────┬──────┬──────┬────────┬────────┬──────────┐   ║
║ │ Model      │ MAE  │ RMSE │ R²   │Acc@0.5 │ Acc@1.0│ Time(s)  │   ║
║ ├────────────┼──────┼──────┼──────┼────────┼────────┼──────────┤   ║
║ │ KNN        │ 0.38 │ 0.51 │ 0.89 │  82%   │  96%   │   0.2    │   ║
║ │            │  🏆  │  🏆  │  🏆  │   🏆   │   🏆   │    🏆    │   ║
║ ├────────────┼──────┼──────┼──────┼────────┼────────┼──────────┤   ║
║ │ Kernel Reg │ 0.44 │ 0.58 │ 0.86 │  76%   │  93%   │   0.7    │   ║
║ ├────────────┼──────┼──────┼──────┼────────┼────────┼──────────┤   ║
║ │ LWLR       │ 0.41 │ 0.55 │ 0.87 │  79%   │  95%   │   1.3    │   ║
║ └────────────┴──────┴──────┴──────┴────────┴────────┴──────────┘   ║
║                                                                       ║
║ ┌───────────────────────────────────────────────────────────────┐   ║
║ │ 🏆 RECOMMENDATION                                             │   ║
║ │                                                               │   ║
║ │ Best Model: K-Nearest Neighbors (KNN)                         │   ║
║ │                                                               │   ║
║ │ Reasons:                                                      │   ║
║ │ ✓ Lowest MAE (0.45, 0.38) across both tasks                 │   ║
║ │ ✓ Highest accuracy at 0.5 threshold (78%, 82%)              │   ║
║ │ ✓ Fastest inference time (0.2s)                              │   ║
║ │ ✓ Best R² score (0.85, 0.89) - explains variance well       │   ║
║ │                                                               │   ║
║ │ 💡 Suggestion: Keep using KNN with n_neighbors=15            │   ║
║ └───────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

### 3.7. Notifications

**Notification Bell Dropdown:**
```
                          ╔═══════════════════════════╗
                          ║ 🔔 THÔNG BÁO        [⚙️] ║
                          ╟───────────────────────────╢
                          ║                           ║
                          ║ ● Điểm Toán đã cập nhật  ║
                          ║   2 phút trước            ║
                          ║   [Xem chi tiết →]       ║
                          ║                           ║
                          ║ ● Có 6 dự đoán mới       ║
                          ║   10 phút trước           ║
                          ║   [Xem biểu đồ →]        ║
                          ║                           ║
                          ║ ○ Model đã thay đổi      ║
                          ║   1 giờ trước             ║
                          ║                           ║
                          ║ ○ Dataset updated         ║
                          ║   Hôm qua                 ║
                          ║                           ║
                          ║───────────────────────────║
                          ║ [Xem tất cả (15)]         ║
                          ║ [Đánh dấu đã đọc]        ║
                          ╚═══════════════════════════╝
```

**Toast Notification:**
```
     ╔═══════════════════════════════════════╗
     ║ ✅ Thành công!                        ║
     ║ Đã cập nhật điểm Toán HK1 L10 = 8.5  ║
     ║ Đang tính toán dự đoán mới...        ║
     ╚═══════════════════════════════════════╝
                                      [✕]
```

---

**Phần 3 hoàn tất: Screenshots mô phỏng giao diện**

Đã mô phỏng:
- ✅ Login & Authentication screens
- ✅ Dashboard overview
- ✅ Chatbot interface với pending confirmations
- ✅ Study scores management table
- ✅ Data visualization charts (Line, Bar, Radar)
- ✅ Developer dashboard (Dataset, Model, Evaluation)
- ✅ Notifications (Bell, Toast)

Trong response tiếp theo sẽ là **Phần 4: Kết quả đánh giá mô hình**.
