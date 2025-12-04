## EduTwin - Bản Sao Học Tập Kỹ Thuật Số
Dự án EduTwin với mục tiêu không chỉ là một nền tảng hỗ trợ học tập thông minh mà còn là một bản sao của bạn trong các vấn đề về học tập, cá nhân hóa trải nghiệm giáo dục cho từng người dùng. Lấy cảm hứng từ sự phát triển của trí tuệ nhân tạo và công nghệ học máy, EduTwin hướng đến việc cung cấp các giải pháp học tập hiện đại, hỗ trợ người học đạt được mục tiêu giáo dục của mình một cách hiệu quả.
Bối cảnh của dự án xuất phát từ nhu cầu ngày càng tăng về các công cụ học tập trực tuyến, đặc biệt là những công cụ có khả năng hiểu và đáp ứng nhu cầu riêng biệt của từng cá nhân. EduTwin với pipeline Machine Learning (ML) tối ưu kết hợp với mô hình ngôn ngữ lớn (LLM) và các kỹ thuật truy xuất không chỉ là ứng dụng đơn thuần mà có khả năng tương tác chủ động - cập nhật dữ liệu trong quá trình sử dụng - tạo nên một vòng tiến hóa liên tục cho hệ thống.
Với sự kết hợp giữa công nghệ tiên tiến và tầm nhìn giáo dục, EduTwin hứa hẹn sẽ trở thành một người bạn đồng hành đáng tin cậy trên hành trình học tập của mỗi cá nhân.

## Tổng quan hệ thống
```mermaid
flowchart TB
    subgraph Users["👥 NGƯỜI DÙNG"]
        Student["👨‍🎓 Học sinh/Sinh viên"]
        Teacher["👨‍🏫 Giáo viên"]
    end

    subgraph Frontend["🎨 FRONTEND"]
        React["React + Vite + TailwindCSS"]
        Features1["✨ Tính năng:<br/>- Dashboard học tập<br/>- Chatbot AI<br/>- Dự đoán điểm số<br/>- Quản lý mục tiêu<br/>- Tùy chỉnh mô hình<br/>- Quản lý hệ thống"]
    end

    subgraph Backend["⚙️ BACKEND"]
        FastAPI["FastAPI + Python"]
        Features2["✨ Tính năng:<br/>- API RESTful<br/>- Authentication<br/>- Data Processing"]
    end

    subgraph ML["🤖 AI/ML - Trí tuệ nhân tạo"]
        MLModels["ML Models"]
        Features3["✨ Tính năng:<br/>- Chatbot thông minh (LLM)<br/>- Cá nhân hóa học tập (KNN)<br/>- Dự đoán hiệu suất<br/>- Phân tích học tập"]
    end

    subgraph Database["💾 DATABASE - Lưu trữ dữ liệu"]
        Postgres["PostgreSQL<br/>(Dữ liệu người dùng)"]
        Redis["Redis<br/>(Cache & Session)"]
        S3["S3<br/>(Files & Assets)"]
    end

    subgraph DevOps["🚀 CI/CD PIPELINE"]
        Step1["1️⃣ Code Push<br/>(GitHub)"]
        Step2["2️⃣ Auto Build & Test<br/>(GitHub Actions)"]
        Step3["3️⃣ Docker Build<br/>(Containerize)"]
        Step4["4️⃣ Deploy to AWS<br/>(ECS/ECR)"]
        
        Step1 --> Step2 --> Step3 --> Step4
    end

    subgraph AWS["☁️ AWS CLOUD INFRASTRUCTURE"]
        ECS["ECS Containers<br/>(Chạy ứng dụng)"]
        RDS["RDS PostgreSQL<br/>(Database)"]
        LoadBalancer["Load Balancer<br/>(Phân phối tải)"]
        CloudWatch["CloudWatch + Grafana<br/>(Monitoring)"]
    end

    %% User Flow
    Student --> Frontend
    Teacher --> Frontend
    
    %% Application Flow
    Frontend --> Backend
    Backend --> ML
    Backend --> Database
    
    %% Database connections
    Postgres -.-> Database
    Redis -.-> Database
    S3 -.-> Database
    
    %% Deploy Flow
    Step4 --> AWS
    
    %% AWS Components
    LoadBalancer --> ECS
    ECS --> RDS
    ECS -.-> CloudWatch

    %% Styling
    classDef userStyle fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef frontendStyle fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef backendStyle fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    classDef mlStyle fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef dataStyle fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef devopsStyle fill:#e0f2f1,stroke:#00796b,stroke-width:2px
    classDef awsStyle fill:#fff9c4,stroke:#f57f17,stroke-width:2px

    class Student,Teacher userStyle
    class React,Features1 frontendStyle
    class FastAPI,Features2 backendStyle
    class MLModels,Features3 mlStyle
    class Postgres,Redis,S3 dataStyle
    class Step1,Step2,Step3,Step4 devopsStyle
    class ECS,RDS,LoadBalancer,CloudWatch awsStyle
```
## Các tính năng chính
- pipeline dự đoán điểm số: 
## Hướng phát triển
- Tăng cường chi tiết tính năng: Hiện tại mức độ chi tiết của các tác vụ dự đoán đang bị giới hạn bởi tập dữ liệu tham chiếu, nếu có khả năng thu thập các tập dữ liệu chi tiết với các thông tin như:
hoàn cảnh gia đình, môn học năng khiếu, thời gian học, chương trình phụ đạo, khóa học online,... thì sẽ trực đưa ra được các dự đoán chi tiết hơn -> nhiều thông tin hơn -> LLM phản hồi chính xác và chi tiết hơn -> tăng cường cá nhân hóa thông qua việc đưa ra các đề xuấ, phân tích, lộ trình riêng cho từng học sinh.
- Tăng cường tính chuyên môn của hệ thống: Huấn luyện và tự deploy LLM chuyên môn trong tác vụ giáo dục -> tăng cường độ chính xác phản hồi, không phụ thuộc và LLM API của bên thứ 3, tăng cường bảo mật thông tin.
- Tăng cường tính hệ thống và tự động hóa: Kết nối đến các cơ sở dữ liệu của trường/tổ chức để tự động update mỗi khi có dữ liệu mới thay vì nhập thủ công (như SMAS và VNEDU)
