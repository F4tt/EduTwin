## EduTwin - Bản Sao Học Tập Kỹ Thuật Số
Dự án EduTwin với mục tiêu không chỉ là một nền tảng hỗ trợ học tập thông minh mà còn là một bản sao của bạn trong các vấn đề về học tập, cá nhân hóa trải nghiệm giáo dục cho từng người dùng. Lấy cảm hứng từ sự phát triển của trí tuệ nhân tạo và công nghệ học máy, EduTwin hướng đến việc cung cấp các giải pháp học tập hiện đại, hỗ trợ người học đạt được mục tiêu giáo dục của mình một cách hiệu quả.
Bối cảnh của dự án xuất phát từ nhu cầu ngày càng tăng về các công cụ học tập trực tuyến, đặc biệt là những công cụ có khả năng hiểu và đáp ứng nhu cầu riêng biệt của từng cá nhân. EduTwin với pipeline Machine Learning (ML) tối ưu kết hợp với mô hình ngôn ngữ lớn (LLM) và các kỹ thuật truy xuất không chỉ là ứng dụng đơn thuần mà có khả năng tương tác chủ động - cập nhật dữ liệu trong quá trình sử dụng - tạo nên một vòng tiến hóa liên tục cho hệ thống.
Với sự kết hợp giữa công nghệ tiên tiến và tầm nhìn giáo dục, EduTwin hứa hẹn sẽ trở thành một người bạn đồng hành đáng tin cậy trên hành trình học tập của mỗi cá nhân.



## Các tính năng chính
1. dự đoán điểm số:
- 3 mô hình Lazy Learning (LL) KNN,Kernel Resgression, LWLR được lựa chọn thay vì các mô hình DL bởi khả năng thích nghi tốt trong bối cảnh giáo dục phức tạp (mỗi trường/trung tâm/sơ sở có các chương trình, môn học khác nhau) -> 3 mô hình LL cho phép thích nghi tốt với input features và ouput labels không cố định, cho phép tạo custom model theo chương trình học của từng học sinh -> tăng tính cá nhân hóa theo đúng muc tiêu EduTwin.
<img width="1183" height="768" alt="image" src="https://github.com/user-attachments/assets/fe317062-d609-4d42-ad93-51107794d5ba" />
- Trực quan hóa kết quả dự đoán:
<img width="1919" height="991" alt="image" src="https://github.com/user-attachments/assets/0a10f0fd-83f6-4c10-9129-0038b7b8e58d" />
<img width="1913" height="981" alt="image" src="https://github.com/user-attachments/assets/ea6ca9dd-77a5-429b-a80f-72ce2e79caf2" />
<img width="1919" height="984" alt="image" src="https://github.com/user-attachments/assets/d153a332-51d2-4a1b-9839-735b8817427f" />

- Thiết lập mục tiêu: không chỉ dự đoán truyền thống -> học sinh có thể xác định một mục tiêu tương lai và hệ thống sẽ dự đoán - vẽ lộ trình để đạt mục tiêu -> tính thích nghi của mô hình LL.
<img width="1919" height="989" alt="image" src="https://github.com/user-attachments/assets/b98fe109-f4fc-4778-82ed-81f0a13fe1ea" />
<img width="1918" height="987" alt="image" src="https://github.com/user-attachments/assets/b1e8e52b-b286-496a-b193-d2581a5008e7" />
- Tự tạo ra các mô hình theo nhu cầu bản thân:
<img width="1917" height="986" alt="Ảnh chụp màn hình 2025-12-04 201310" src="https://github.com/user-attachments/assets/fe469ae9-98a7-4364-a507-67ba30c37573" />
<img width="1917" height="983" alt="Ảnh chụp màn hình 2025-12-04 201433" src="https://github.com/user-attachments/assets/7ec928d1-e9ac-49ef-8aa9-72d0d2f490be" />
<img width="1918" height="985" alt="Ảnh chụp màn hình 2025-12-04 201650" src="https://github.com/user-attachments/assets/9e8b2885-57a8-494a-aa84-fc6885fa4742" />

2. Chatbot thông minh - LLM API.
- Giao diện thân thiện, hỗ trợ phân tích cách thông tin học tập. Không chỉ vậy, còn có khả năng trò chuyện chủ động để cuộc trò chuyện như hai người bạn và học tập các thông tin cá nhân hóa -> dùng cho các response và phân tích.
<img width="1919" height="991" alt="Ảnh chụp màn hình 2025-12-04 202511" src="https://github.com/user-attachments/assets/2af3126f-f506-4549-bf6e-3e55d48e8885" />
<img width="1919" height="984" alt="Ảnh chụp màn hình 2025-12-04 202143" src="https://github.com/user-attachments/assets/135c1ee8-4381-405b-ae8c-f609b891cb1d" />
<img width="1342" height="435" alt="Ảnh chụp màn hình 2025-12-04 203139" src="https://github.com/user-attachments/assets/48375ca3-5f54-4bf5-b444-328110b662a7" />
<img width="1014" height="367" alt="Ảnh chụp màn hình 2025-12-04 203013" src="https://github.com/user-attachments/assets/1fdc32bc-2b7d-43fc-8549-4ae05dcfbb3a" />

3. Vòng lặp liên tục giúp hệ thống tiến hóa trong quá trình sử dụng.
- Quá trình trò chuyện -> yêu cầu từ người dùng -> intent detection -> xác nhận từ người dùng -> cập nhật vào database -> kích hoạt pipeline ML -> kết quả dự đoán mới -> gửi cho LLM -> response -> yêu cầu từ người dùng.... Đảm bảo thông tin và dự đoán được làm mới liên tục, các thông tin cá nhân cũng được thu thập để hoàn thiện phản hồi của Twin.
<img width="1326" height="835" alt="Ảnh chụp màn hình 2025-12-04 203320" src="https://github.com/user-attachments/assets/9598732d-8afe-4f09-b8df-c65862cef0ab" />

4. Phân quyền và quản lý hệ thống.
- Cho phép người dùng role Admin quản lý tập dữ liệu tham chiếu cho LL model, tinh chỉnh tham số, đánh giá mô hình, lựa chọn mô hình được áp dụng -> người quản trị có thể upload tập dữ liệu của trường/cơ sở của mình và lựa chọn mô hình phù hợp -> tăng độ chính xác đối với các dự đoán cho học sinh của trường/cơ sở đó bởi bias của tập dữ liệu tốt hơn.
<img width="1918" height="986" alt="Ảnh chụp màn hình 2025-12-04 203644" src="https://github.com/user-attachments/assets/0bf37924-ce2b-4426-abdc-79d50fefdd9f" />
<img width="1917" height="983" alt="Ảnh chụp màn hình 2025-12-04 204006" src="https://github.com/user-attachments/assets/d4efb3d3-d289-4227-9ad4-9bf363a1da5b" />
<img width="1919" height="982" alt="Ảnh chụp màn hình 2025-12-04 204146" src="https://github.com/user-attachments/assets/03917951-580c-4469-a249-aaa3cf4ca7b1" />


## Tại sao EduTwin
- So với các hệ thống hỗ trợ giáo dục truyền thống (SMAS - Viettel, VNEDU - VNPT, Google Classroom): chỉ đơn giản là kết nối tới cơ sở dữ liệu cho phép xem kết quả học tập -> EduTwin không chỉ giám sát mà còn dự đoán, phân tích, cá nhân hóa, và tự xây dựng mô hình học tập của riêng bạn.
- So với các mô hình DL: EduTwin linh động, đễ dàng mở rộng và có khả năng custom theo chương trình học, ngoài dự đoán đơn thuần EduTwin còn tích hợp LLM cho phép phân tích, trò chuyện và kết hợp các thông tin cá nhân vào phản hồi.
- So với các AI chatbot (ChatGPT, Gemini,...): bị ảo giác, không lưu trữ khiến mất mát thông tin -> EduTwin lưu trữ thông tin học tập, chuyên biệt cho tác vụ học tập, kết quả và số liệu được tính toán từ hệ thống và kết quả dự đoán của LL model là minh bạch, có thể kiểm chứng.


## Khó khăn:
- nguồn lực cá nhân hạn chế khiến:
+ Tập dữ liệu tham chiếu cho LL model bị hạn chế -> giới hạn về phạm vi và độ chi tiết của các dự đoán.
+ Khó xây dựng tập dữ liệu finetune LLM và deploy -> phụ thuộc vào LLM API từ bên thứ 3, các LLM API không chuyên hóa lĩnh vực giáo dục.
## Hướng phát triển
- Tăng cường chi tiết tính năng: Hiện tại mức độ chi tiết của các tác vụ dự đoán đang bị giới hạn bởi tập dữ liệu tham chiếu, nếu có khả năng thu thập các tập dữ liệu chi tiết với các thông tin như:
hoàn cảnh gia đình, môn học năng khiếu, thời gian học, chương trình phụ đạo, khóa học online,... thì sẽ trực đưa ra được các dự đoán chi tiết hơn -> nhiều thông tin hơn -> LLM phản hồi chính xác và chi tiết hơn -> tăng cường cá nhân hóa thông qua việc đưa ra các đề xuấ, phân tích, lộ trình riêng cho từng học sinh.
- Tăng cường tính chuyên môn của hệ thống: Huấn luyện và tự deploy LLM chuyên môn trong tác vụ giáo dục -> tăng cường độ chính xác phản hồi, không phụ thuộc và LLM API của bên thứ 3, tăng cường bảo mật thông tin.
- Tăng cường tính hệ thống và tự động hóa: Kết nối đến các cơ sở dữ liệu của trường/tổ chức để tự động update mỗi khi có dữ liệu mới thay vì nhập thủ công (như SMAS và VNEDU)

# EduTwin - Sơ đồ Kiến trúc Hệ thống

## 📊 Tổng quan Kiến trúc

```mermaid
flowchart TB
    subgraph CLIENT["🖥️ CLIENT LAYER"]
        direction LR
        subgraph REACT["React 19 + Vite 7"]
            M1[" AI Chatbot"]
            M2[" Data Viz"]
            M3[" Score Mgmt"]
            M4[" Setting"]
            M5[" Dev Tools"]
        end
    end

    subgraph AWS["☁️ AWS CLOUD INFRASTRUCTURE"]
        direction TB
        ALB["⚖️ Application Load Balancer"]
        
        subgraph ECS["📦 ECS Cluster"]
            FE["⚛️ Frontend Container<br/>React + Nginx"]
            BE["🐍 Backend Container<br/>FastAPI + Python 3.11"]
        end
        
        subgraph DATA["💾 Data Tier"]
            RDS[("🐘 PostgreSQL 15<br/>User Data | Scores")]
            REDIS[("⚡ Redis 7<br/>Cache | Sessions")]
            S3["🪣 S3<br/>Documents"]
        end
    end

    subgraph AIML["🧠 AI/ML CORE"]
        direction TB
        subgraph LAZY["🎯 Lazy Learning Engine"]
            KNN["KNN"]
            LWLR["LWLR"]
            KR["Kernel Regression"]
            CLUSTER["Cluster + Prototype"]
        end
        
        subgraph LLM["💬 LLM Integration"]
            CTX["Context Builder"]
            INTENT["Intent Detection"]
            PII["PII Redaction"]
        end
        
        subgraph STACK["📊 ML Stack"]
            SK["Scikit-learn"]
            NP["NumPy + Pandas"]
            CACHE["Prediction Cache"]
        end
    end

    subgraph EXTERNAL["🔗 External"]
        VNPT["VNPT SmartBot<br/>LLM API"]
    end

    subgraph OBS["📡 OBSERVABILITY"]
        GH["🐙 GitHub Actions"]
        PROM["🔥 Prometheus"]
        GRAF["📊 Grafana"]
        LOKI["📝 Loki"]
    end

    subgraph IAC["🏗️ IaC"]
        TF["🟣 Terraform 1.5+"]
    end

    %% Connections
    CLIENT --> ALB
    ALB --> FE
    ALB --> BE
    BE --> RDS
    BE --> REDIS
    BE --> S3
    BE --> LAZY
    BE --> LLM
    LLM --> VNPT
    LAZY --> CACHE
    CACHE --> REDIS
    OBS -.-> AWS
    TF -.-> AWS

    %% Styling
    classDef clientStyle fill:#4f46e5,stroke:#7c3aed,color:#fff
    classDef awsStyle fill:#ff9900,stroke:#cc7700,color:#fff
    classDef aiStyle fill:#10b981,stroke:#059669,color:#fff
    classDef obsStyle fill:#8b5cf6,stroke:#6366f1,color:#fff
    classDef externalStyle fill:#ef4444,stroke:#dc2626,color:#fff

    class CLIENT clientStyle
    class AWS awsStyle
    class AIML aiStyle
    class OBS obsStyle
    class EXTERNAL externalStyle
```

---

## 🔄 Data Flow Diagrams

### User Request Flow
```mermaid
sequenceDiagram
    participant U as 👤 User
    participant FE as ⚛️ Frontend
    participant ALB as ⚖️ ALB
    participant BE as 🐍 Backend
    participant DB as 🐘 PostgreSQL
    participant CACHE as ⚡ Redis

    U->>FE: User Action
    FE->>ALB: HTTP Request
    ALB->>BE: Route to Backend
    BE->>CACHE: Check Cache
    alt Cache Hit
        CACHE-->>BE: Cached Data
    else Cache Miss
        BE->>DB: Query Database
        DB-->>BE: Data
        BE->>CACHE: Store in Cache
    end
    BE-->>ALB: Response
    ALB-->>FE: HTTP Response
    FE-->>U: Update UI
```

### ML Prediction Flow
```mermaid
sequenceDiagram
    participant REQ as 📥 Request
    participant SVC as 🎯 Prediction Service
    participant CACHE as ⚡ Redis Cache
    participant IDX as 📊 Cluster Index
    participant ML as 🧠 Lazy Learning
    
    REQ->>SVC: Prediction Request
    SVC->>CACHE: Check Prediction Cache
    alt Cache Hit
        CACHE-->>SVC: Cached Prediction
    else Cache Miss
        SVC->>IDX: Assign Cluster
        IDX-->>SVC: Cluster ID
        SVC->>ML: Get Prototypes
        ML->>ML: KNN/KR/LWLR Calculation
        ML-->>SVC: Predictions
        SVC->>CACHE: Cache Predictions
    end
    SVC-->>REQ: Return Predictions
```

### AI Chatbot Flow
```mermaid
sequenceDiagram
    participant U as 👤 User
    participant CHAT as 💬 Chatbot API
    participant INTENT as 🔍 Intent Detection
    participant CTX as 📋 Context Builder
    participant PII as 🔒 PII Redaction
    participant LLM as 🤖 LLM API

    U->>CHAT: User Message
    CHAT->>INTENT: Detect Intent
    INTENT-->>CHAT: Intent (score_update/general)
    alt Score Update Intent
        CHAT->>CHAT: Handle Score Update
        CHAT-->>U: Confirmation
    else General Query
        CHAT->>CTX: Build Context
        CTX->>CTX: Gather User History<br/> Scores, Preferences
        CTX-->>CHAT: Rich Context
        CHAT->>PII: Redact PII
        PII-->>CHAT: Safe Context
        CHAT->>LLM: API Call with Context
        LLM-->>CHAT: AI Response
        CHAT-->>U: Personalized Response
    end
```

---

## 🏗️ Component Architecture

```mermaid
graph TB
    subgraph "Frontend (React 19)"
        APP[App.jsx]
        AUTH[Auth.jsx]
        VIZ[DataViz.jsx]
        CHAT[Chatbot.jsx]
        STUDY[StudyUpdate.jsx]
        DEV[Developer.jsx]
        
        APP --> AUTH
        APP --> VIZ
        APP --> CHAT
        APP --> STUDY
        APP --> DEV
    end

    subgraph "Backend (FastAPI)"
        MAIN[main.py]
        
        subgraph "API Layer"
            A1[auth.py]
            A2[user.py]
            A3[chatbot.py]
            A4[developer.py]
            A5[custom_model.py]
        end
        
        subgraph "Services"
            S1[chatbot_service.py]
            S2[intent_detection.py]
            S3[pii_redaction.py]
            S4[llm_provider.py]
            S5[personalization.py]
        end
        
        subgraph "ML Module"
            ML1[prediction_service.py]
            ML2[cluster_prototype.py]
            ML3[prediction_cache.py]
        end
        
        MAIN --> A1 & A2 & A3 & A4 & A5
        A3 --> S1 & S2 & S3 & S4
        A5 --> ML1 & ML2 & ML3
    end
```

---

## 📊 Technology Stack Summary

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | React | 19.2.0 | UI Framework |
| | Vite | 7.2.4 | Build Tool |
| | Recharts | Latest | Data Visualization |
| **Backend** | FastAPI | 0.100+ | API Framework |
| | Python | 3.11 | Runtime |
| | SQLAlchemy | 2.0 | ORM |
| **Database** | PostgreSQL | 15 | Primary DB |
| | Redis | 7 | Cache & Sessions |
| **ML Stack** | Scikit-learn | Latest | ML Framework |
| | NumPy | Latest | Numerical Computing |
| | Pandas | Latest | Data Processing |
| **Cloud** | AWS ECS | - | Container Orchestration |
| | AWS RDS | - | Managed PostgreSQL |
| | AWS S3 | - | Object Storage |
| **IaC** | Terraform | 1.5+ | Infrastructure |
| **CI/CD** | GitHub Actions | - | Automation |
| **Observability** | Prometheus | Latest | Metrics |
| | Grafana | Latest | Dashboards |
| | Loki | Latest | Logs |

---

## 🎯 Key Architecture Decisions

### 1. Lazy Learning over Eager Learning
```
┌─────────────────────────────────────────────────────────────┐
│  LAZY LEARNING (EduTwin)          │  EAGER LEARNING        │
├─────────────────────────────────────────────────────────────┤
│  ✅ No retraining needed          │  ❌ Costly retraining  │
│  ✅ Instant structure adaptation  │  ❌ Structure lock-in  │
│  ✅ Real-time predictions         │  ⚠️ Batch predictions  │
│  ⚠️ O(n) query time              │  ✅ O(1) predictions   │
│                                                             │
│  💡 SOLUTION: Cluster + Prototype Optimization              │
│     → Reduces effective query time to O(k) where k << n     │
└─────────────────────────────────────────────────────────────┘
```

### 2. Multi-tier Caching Strategy
```
┌─────────────────────────────────────────────┐
│ Level 1: In-Memory (Hot Data)               │
├─────────────────────────────────────────────┤
│ Level 2: Redis (Predictions, Sessions)      │
├─────────────────────────────────────────────┤
│ Level 3: PostgreSQL (Persistent)            │
└─────────────────────────────────────────────┘
```

### 3. Privacy-First LLM Integration
```
User Message → Intent Detection → Context Building → PII Redaction → LLM API
                                                        ↓
                                              ✓ Emails masked
                                              ✓ Phones redacted
                                              ✓ Addresses anonymized
```

---

## 🚀 Deployment Architecture

```mermaid
graph TB
    subgraph "Development"
        DEV_LOCAL["🖥️ Local Docker Compose"]
    end

    subgraph "CI/CD Pipeline"
        GH["GitHub Actions"]
        GH --> BUILD["Build & Test"]
        BUILD --> ECR["Push to ECR"]
    end

    subgraph "Production (AWS)"
        ECR --> ECS["ECS Fargate"]
        ECS --> ALB["Application LB"]
        ALB --> USERS["🌐 Users"]
    end

    DEV_LOCAL -.->|Push| GH
```
