import streamlit as st
import requests
import os
from datetime import datetime
from typing import Dict, List, Any

API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


# Map from no-diacritics (database storage) to display names with diacritics
SUBJECT_DISPLAY_MAP = {
    "Toan": "Toán",
    "Ngu van": "Ngữ văn",
    "Vat ly": "Vật lý",
    "Hoa hoc": "Hóa học",
    "Sinh hoc": "Sinh học",
    "Lich su": "Lịch sử",
    "Dia ly": "Địa lý",
    "Tieng Anh": "Tiếng Anh",
    "Giao duc cong dan": "Giáo dục công dân",
}

STUDY_SUBJECTS = [
    "Toan",
    "Ngu van",
    "Tieng Anh",
    "Vat ly",
    "Hoa hoc",
    "Sinh hoc",
    "Lich su",
    "Dia ly",
    "Giao duc cong dan",
]

# Subject groupings for blocks
KHOI_XH_SUBJECTS = {"Toan", "Ngu van", "Tieng Anh", "Lich su", "Dia ly", "Giao duc cong dan"}
KHOI_TN_SUBJECTS = {"Toan", "Ngu van", "Tieng Anh", "Vat ly", "Hoa hoc", "Sinh hoc"}

# Exam blocks (A00, B00, C00, D01)
EXAM_BLOCKS = {
    "A00": {"Toan", "Vat ly", "Hoa hoc"},
    "B00": {"Toan", "Hoa hoc", "Sinh hoc"},
    "C00": {"Ngu van", "Lich su", "Dia ly"},
    "D01": {"Ngu van", "Toan", "Tieng Anh"},
}

STUDY_GRADE_ORDER = ["10", "11", "12"]
STUDY_SEMESTER_ORDER: Dict[str, List[str]] = {
    "10": ["1", "2"],
    "11": ["1", "2"],
    "12": ["1", "2"]
}
STUDY_GRADE_DISPLAY = {
    "10": "Lớp 10",
    "11": "Lớp 11",
    "12": "Lớp 12"
}
STUDY_SEMESTER_DISPLAY = {"1": "Học kỳ 1", "2": "Học kỳ 2"}
DEFAULT_SCORE_PLACEHOLDER = "VD: 8.5"


def get_api_session() -> requests.Session:
    if "api_session" not in st.session_state:
        st.session_state.api_session = requests.Session()
    return st.session_state.api_session


def is_valid_username(username: str) -> bool:
    return bool(username) and username.isascii() and all(ch.isalnum() or ch in {"_", "-"} for ch in username)


def is_ascii_text(value: str) -> bool:
    return bool(value) and value.isascii()


def get_subject_display_name(subject_code: str) -> str:
    """Convert subject code (no-diacritics) to display name (with diacritics)."""
    return SUBJECT_DISPLAY_MAP.get(subject_code, subject_code)

# =============== Styles ===============
PRIMARY_RED = "#d32f2f"


def inject_global_styles():
    sidebar_css = f"""
    <style>
    section[data-testid="stSidebar"] {{
        background: #f2f2f2 !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        background: #ffffff !important;
        color: {PRIMARY_RED} !important;
        border: 1px solid #dddddd !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: #e9e9e9 !important;
        border-color: #cccccc !important;
    }}
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background: {PRIMARY_RED} !important;
        color: #ffffff !important;
        border-color: {PRIMARY_RED} !important;
    }}
    .score-status {{
        display: flex;
        justify-content: flex-end;
        align-items: center;
        margin-top: 4px;
    }}
    .score-badge {{
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
    }}
    .score-badge.actual {{
        background: #e8f5e9;
        color: #2e7d32;
    }}
    .score-badge.predicted {{
        background: #e3f2fd;
        color: #1565c0;
    }}
    .score-badge.empty {{
        background: #f5f5f5;
        color: #616161;
    }}
    </style>
    """
    st.markdown(sidebar_css, unsafe_allow_html=True)


def fetch_study_scores():
    session = get_api_session()
    try:
        res = session.get(f"{API_URL}/study/scores", timeout=10)
        if res.status_code == 200:
            return res.json(), None
        try:
            detail = res.json().get("detail", res.text)
        except Exception:
            detail = res.text
        return None, detail
    except requests.RequestException as exc:
        return None, str(exc)


def prepare_score_inputs(scores):
    if "study_form_values" not in st.session_state:
        st.session_state.study_form_values = {}
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        grade: {sem: [] for sem in STUDY_SEMESTER_ORDER[grade]} for grade in STUDY_GRADE_ORDER
    }
    score_keys: List[str] = []
    for item in scores:
        key = item["key"]
        score_keys.append(key)
        actual = item.get("actual")
        if key not in st.session_state.study_form_values:
            if actual is None:
                st.session_state.study_form_values[key] = ""
            else:
                try:
                    st.session_state.study_form_values[key] = f"{float(actual):.1f}"
                except (TypeError, ValueError):
                    st.session_state.study_form_values[key] = str(actual)
        if key not in st.session_state:
            st.session_state[key] = st.session_state.study_form_values.get(key, "")
        grade = item["grade_level"]
        semester = item["semester"]
        if grade in grouped and semester in grouped[grade]:
            grouped[grade][semester].append(item)
    return grouped, score_keys


st.set_page_config(page_title="EduTwin", page_icon="🎓", layout="wide")
inject_global_styles()

# =============== Session State ===============
def init_state():
    if "route" not in st.session_state:
        st.session_state.route = "auth"  # auth | first_time | chat | data | settings | developer
    if "prev_route" not in st.session_state:
        st.session_state.prev_route = None
    if "auth_tab" not in st.session_state:
        st.session_state.auth_tab = "login"
    if "user" not in st.session_state:
        st.session_state.user = None
    if "profile" not in st.session_state:
        st.session_state.profile = {"name": "", "email": "", "phone": "", "address": "", "age": ""}
    if "is_first_login" not in st.session_state:
        st.session_state.is_first_login = False
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = {}
    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = None
    if "study_info" not in st.session_state:
        st.session_state.study_info = {
            "grade": "",
            "subjects": "",
            "goal": "",
            "daily_minutes": 60,
        }
    if "pending_score_update" not in st.session_state:
        st.session_state.pending_score_update = None
    if "last_knn_import_summary" not in st.session_state:
        st.session_state.last_knn_import_summary = None


def set_route(route: str, remember_prev: bool = False):
    if remember_prev:
        st.session_state.prev_route = st.session_state.route
    st.session_state.route = route
    st.rerun()


def ensure_first_login_route():
    if (
        st.session_state.get("user")
        and st.session_state.get("is_first_login")
        and st.session_state.route not in ("auth", "first_time")
    ):
        set_route("first_time")


# =============== Auth Views ===============
def render_auth():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            if st.session_state.auth_tab == "login":
                st.markdown("<h3 style='text-align: center;'>Đăng nhập</h3>", unsafe_allow_html=True)
                username_input = st.text_input("Tên đăng nhập", key="login_username", placeholder="Tên đăng nhập")
                password = st.text_input("Mật khẩu", key="login_password", type="password", placeholder="Mật khẩu")
                if st.button("Đăng nhập", type="primary", use_container_width=True):
                    username = username_input.strip()
                    if not username or not password:
                        st.error("Vui lòng điền đầy đủ thông tin!")
                    elif not is_valid_username(username):
                        st.error("Tên đăng nhập chỉ được dùng chữ cái/số tiếng Anh (kèm '_' hoặc '-')")
                    elif not is_ascii_text(password):
                        st.error("Mật khẩu chỉ được dùng ký tự tiếng Anh")
                    else:
                        session = get_api_session()
                        try:
                            res = session.post(
                                f"{API_URL}/auth/login",
                                json={"username": username, "password": password},
                                timeout=10,
                            )
                            if res.status_code == 200:
                                user_data = res.json().get("user", {"username": username})
                                st.session_state.user = user_data
                                full_name = user_data.get("name") or f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                                st.session_state.profile.update({
                                    "name": full_name,
                                    "email": user_data.get("email", ""),
                                    "phone": user_data.get("phone", ""),
                                    "address": user_data.get("address", ""),
                                    "age": user_data.get("age", ""),
                                    "current_grade": user_data.get("current_grade", None),
                                })
                                # Clear any previous user's temporary study form values so the first-time
                                # profile form is clean for the newly logged-in user.
                                if "study_form_values" in st.session_state:
                                    st.session_state.pop("study_form_values", None)
                                # Reset first-time step and pending updates for a fresh start
                                st.session_state.first_time_step = "profile"
                                st.session_state.pending_score_update = None
                                # Prefer server-provided flag if available to avoid client-side inference errors
                                server_first_flag = user_data.get("is_first_login")
                                if server_first_flag is not None:
                                    st.session_state.is_first_login = bool(server_first_flag)
                                else:
                                    st.session_state.is_first_login = not (
                                        st.session_state.profile.get("email") or st.session_state.profile.get("phone")
                                    )
                                set_route("first_time" if st.session_state.is_first_login else "chat")
                            else:
                                msg = res.json().get("detail", "Sai tên đăng nhập hoặc mật khẩu.")
                                st.error(msg)
                        except requests.RequestException as e:
                            st.error(f"Lỗi kết nối: {e}")
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button("Chuyển sang đăng ký", use_container_width=True):
                    st.session_state.auth_tab = "register"
                    st.rerun()

            else:
                st.markdown("<h3 style='text-align: center;'>Đăng ký</h3>", unsafe_allow_html=True)
                last_name = st.text_input("Họ", key="register_lastname", placeholder="VD: Nguyễn")
                first_name = st.text_input("Tên", key="register_firstname", placeholder="VD: Văn A")
                username_input = st.text_input("Tên đăng nhập", key="register_username", placeholder="Tên đăng nhập")
                password = st.text_input("Mật khẩu", key="register_password", type="password", placeholder="Mật khẩu")
                confirm_password = st.text_input("Nhập lại mật khẩu", key="register_confirm", type="password", placeholder="Nhập lại mật khẩu")
                if st.button("Đăng ký", type="primary", use_container_width=True):
                    username = username_input.strip()
                    def _is_valid_letters(s: str) -> bool:
                        return bool(s and all((ch.isalpha() or ch.isspace()) for ch in s))
                    if not last_name or not first_name or not username or not password or not confirm_password:
                        st.error("Vui lòng điền đầy đủ thông tin!")
                    elif not _is_valid_letters(last_name.strip()) or not _is_valid_letters(first_name.strip()):
                        st.error("Họ/Tên chỉ được chứa chữ cái và khoảng trắng.")
                    elif not is_valid_username(username):
                        st.error("Tên đăng nhập chỉ được dùng chữ cái/số tiếng Anh (kèm '_' hoặc '-')")
                    elif not is_ascii_text(password) or not is_ascii_text(confirm_password):
                        st.error("Mật khẩu chỉ được dùng ký tự tiếng Anh")
                    elif password != confirm_password:
                        st.error("Mật khẩu không khớp!")
                    else:
                        session = get_api_session()
                        try:
                            payload = {
                                "first_name": first_name.strip(),
                                "last_name": last_name.strip(),
                                "username": username,
                                "password": password,
                            }
                            res = session.post(f"{API_URL}/auth/register", json=payload, timeout=10)
                            if res.status_code == 200:
                                st.success("Đăng ký thành công! Vui lòng đăng nhập.")
                                st.session_state.auth_tab = "login"
                                st.rerun()
                            else:
                                st.error(res.json().get("detail", "Lỗi đăng ký."))
                        except requests.RequestException as e:
                            st.error(f"Lỗi kết nối: {e}")
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button("Chuyển sang đăng nhập", use_container_width=True):
                    st.session_state.auth_tab = "login"
                    st.rerun()


# =============== First-Time Profile ===============
def validate_profile_fields(email: str, phone: str, address: str, age: str) -> tuple[bool, str]:
    """Kiểm tra tính hợp lệ của các trường thông tin. Trả về (is_valid, error_message)"""
    if email and "@" not in email:
        return False, "Email không hợp lệ. Vui lòng nhập đúng định dạng email."
    
    if phone and not all(c.isdigit() or c.isspace() for c in phone):
        return False, "Số điện thoại chỉ được chứa chữ số và khoảng trắng."
    
    if age:
        try:
            age_int = int(age)
            if age_int < 1 or age_int > 120:
                return False, "Tuổi không hợp lệ. Vui lòng nhập số từ 1 đến 120."
        except ValueError:
            return False, "Tuổi phải là một số nguyên hợp lệ."
    
    return True, ""


def render_first_time_profile():
    st.markdown(
        f"""
        <style>
        div[data-testid="stSidebar"] {{display: none !important;}}
        header {{visibility: hidden;}}
        #MainMenu {{visibility: hidden;}}
        [data-testid="stAppViewContainer"] {{
            background: #fafafa;
        }}
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            margin-bottom: 32px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background: {PRIMARY_RED};
            transition: width 0.3s ease;
        }}
        .step-indicator {{
            text-align: center;
            margin-bottom: 24px;
            color: #666;
            font-size: 14px;
            font-weight: 500;
        }}
        .welcome-title {{
            font-size: 28px;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 12px;
            text-align: center;
        }}
        .welcome-subtitle {{
            font-size: 15px;
            color: #666;
            margin-bottom: 32px;
            text-align: center;
            line-height: 1.6;
        }}
        /* Style cho các nút */
        .stButton > button {{
            height: 48px !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
        }}
        .stButton > button[kind="primary"] {{
            background: {PRIMARY_RED} !important;
            color: white !important;
            border: none !important;
        }}
        .stButton > button[kind="primary"][disabled] {{
            background: #f0a0a0 !important; 
            color: #ffffffcc !important;      
            opacity: 0.6 !important;
            cursor: not-allowed !important;
        }}
        .stButton > button[kind="primary"]:hover {{
            background: #b71c1c !important;
        }}
        .stButton > button:not([kind="primary"]) {{
            background: white !important;
            color: {PRIMARY_RED} !important;
            border: 1px solid #ddd !important;
        }}
        .stButton > button:not([kind="primary"]):hover {{
            background: #f5f5f5 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    step = st.session_state.get("first_time_step", "profile")
    st.session_state.first_time_step = step

    progress_percent = 50 if step == "profile" else 100
    
    st.markdown(f"<div class='step-indicator'>Bước {1 if step == 'profile' else 2} / 2</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='progress-bar'><div class='progress-fill' style='width: {progress_percent}%'></div></div>", unsafe_allow_html=True)

    if step == "profile":
        st.markdown("<div class='welcome-title'>👋 Chào mừng bạn đến với EduTwin</div>", unsafe_allow_html=True)
        st.markdown("<div class='welcome-subtitle'>Hãy bổ sung một vài thông tin để chúng tôi có thể phục vụ bạn tốt hơn.<br>Bạn có thể bỏ qua và hoàn thiện sau nếu muốn.</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            email = st.text_input("📧 Email", value=st.session_state.profile.get("email", "") or "", placeholder="VD: ten@example.com", key="first_profile_email")
            address = st.text_input("🏠 Địa chỉ", value=st.session_state.profile.get("address", "") or "", placeholder="VD: 123 Nguyễn Huệ, Quận 1", key="first_profile_address")
        with col2:
            phone = st.text_input("📱 Số điện thoại", value=st.session_state.profile.get("phone", "") or "", placeholder="VD: 0912 345 678", key="first_profile_phone")
            age = st.text_input("🎂 Tuổi", value=st.session_state.profile.get("age", "") or "", placeholder="VD: 16", key="first_profile_age")
        
        # Đảm bảo các giá trị không None trước khi strip
        email_val = (email or "").strip()
        phone_val = (phone or "").strip()
        address_val = (address or "").strip()
        age_val = (age or "").strip()
        
        has_any_input = any([email_val, phone_val, address_val, age_val])
        is_valid, error_msg = validate_profile_fields(email_val, phone_val, address_val, age_val)
        
        if error_msg:
            st.error(error_msg)
        
        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
        
        col_skip, col_save = st.columns([1, 1])
        
        with col_skip:
            if st.button("⏭️ Bỏ qua", use_container_width=True, key="profile_skip"):
                # Mark onboarding completed on server (so future logins won't show first-time)
                try:
                    session = get_api_session()
                    session.post(f"{API_URL}/auth/complete-first-time", timeout=5)
                except Exception:
                    pass
                st.session_state.first_time_step = "scores"
                st.rerun()
        
        with col_save:
            save_disabled = not has_any_input or not is_valid
            if st.button("💾 Lưu và tiếp tục", type="primary", use_container_width=True, disabled=save_disabled, key="profile_save"):
                # Lưu vào session state
                st.session_state.profile.update({
                    "email": email_val,
                    "phone": phone_val,
                    "address": address_val,
                    "age": age_val,
                })
                
                # Gọi API lưu
                payload = {
                    "email": email_val or None,
                    "phone": phone_val or None,
                    "address": address_val or None,
                    "age": age_val or None,
                }
                session = get_api_session()
                try:
                    res = session.post(f"{API_URL}/auth/profile", json=payload, timeout=10)
                    if res.status_code in (200, 204):
                        profile_data = res.json().get("profile", {}) if res.content else {}
                        for field, value in profile_data.items():
                            st.session_state.profile[field] = value or ""
                except requests.RequestException:
                    pass  # Tiếp tục dù có lỗi

                # Mark onboarding completed on server
                try:
                    session.post(f"{API_URL}/auth/complete-first-time", timeout=5)
                except Exception:
                    pass

                # Chuyển sang slide 2
                st.session_state.first_time_step = "scores"
                st.rerun()

    elif step == "scores":
        st.markdown("<div class='welcome-title'>📚 Nhập điểm các môn học</div>", unsafe_allow_html=True)
        st.markdown("<div class='welcome-subtitle'>Điền những điểm đã có để chúng tôi có thể dự đoán chính xác hơn.<br>Bạn cũng có thể bỏ qua và cập nhật sau.</div>", unsafe_allow_html=True)
        
        data, error = fetch_study_scores()
        if error:
            st.error(f"Không thể tải dữ liệu: {error}")
        else:
            scores = data.get("scores", [])
            grade_display = data.get("grade_display", STUDY_GRADE_DISPLAY)
            semester_display = data.get("semester_display", STUDY_SEMESTER_DISPLAY)
            # Grade selection required for KNN predictions - add "None" option to enforce selection
            grade_options = ["-- Chọn Học kỳ (bắt buộc) --"]  # Default "None" option
            grade_map = {"-- Chọn Học kỳ (bắt buộc) --": None}  # Maps to None
            for g in STUDY_GRADE_ORDER:
                for s in STUDY_SEMESTER_ORDER[g]:
                    display = f"{STUDY_SEMESTER_DISPLAY.get(s, s)} {STUDY_GRADE_DISPLAY.get(g, g)}"
                    value = f"{s}_{g}"
                    grade_options.append(display)
                    grade_map[display] = value

            current_grade_val = st.session_state.profile.get("current_grade") if st.session_state.profile else None
            initial_display = None
            if current_grade_val:
                for disp, val in grade_map.items():
                    if val == current_grade_val:
                        initial_display = disp
                        break
            # Default to "None" option (index 0)
            initial_index = grade_options.index(initial_display) if (initial_display and initial_display in grade_options) else 0
            selected_display = st.selectbox("Hiện bạn đang học lớp mấy?", options=grade_options, index=initial_index)
            selected_grade = grade_map.get(selected_display)

            grouped, score_keys = prepare_score_inputs(scores)
            # Build ordered slots and index mapping for disabling future-grade inputs
            ordered_slots = []
            for g in STUDY_GRADE_ORDER:
                for s in STUDY_SEMESTER_ORDER[g]:
                    ordered_slots.append((g, s))
            key_to_idx = {}
            for idx_slot, (g, s) in enumerate(ordered_slots):
                for subj in grouped.get(g, {}).get(s, []):
                    # grouped entries contain dicts; but mapping by subject/semester/grade
                    pass
            # Helper to get index for a given grade/semester
            def slot_index_for_token(token: str) -> int | None:
                if not token:
                    return None
                try:
                    parts = str(token).split("_")
                    if len(parts) != 2:
                        return None
                    sem, gr = parts[0].upper(), parts[1]
                    for idx_slot, (g, s) in enumerate(ordered_slots):
                        if g == gr and s == sem:
                            return idx_slot
                except Exception:
                    return None
                return None

            selected_idx = slot_index_for_token(selected_grade)
            
            # Kiểm tra xem có điểm hợp lệ nào được nhập không
            def has_valid_scores():
                for key in score_keys:
                    raw_value = str(st.session_state.get(key, "")).strip()
                    if not raw_value:
                        continue
                    try:
                        float(raw_value.replace(",", "."))
                        return True
                    except ValueError:
                        continue
                return False

            for grade in STUDY_GRADE_ORDER:
                with st.expander(f"📖 {grade_display.get(grade, f'Lớp {grade}')}", expanded=(grade == "10")):
                    for semester in STUDY_SEMESTER_ORDER[grade]:
                        st.markdown(f"**{semester_display.get(semester, 'Học kỳ')}**")
                        subjects = grouped.get(grade, {}).get(semester, [])
                        if not subjects:
                            st.info("Chưa có dữ liệu cho mục này.")
                            continue
                        cols = st.columns(3)
                        for idx, item in enumerate(subjects):
                            col = cols[idx % 3]
                            with col:
                                key = item["key"]
                                subject_label = get_subject_display_name(item["subject"])
                                actual = item.get("actual")
                                predicted = item.get("predicted")
                                status_text = "Thực tế" if actual is not None else ("Dự đoán" if predicted is not None else "Chưa có")
                                placeholder_value = DEFAULT_SCORE_PLACEHOLDER
                                if predicted is not None and actual is None:
                                    try:
                                        placeholder_value = f"{float(predicted):.1f}"
                                    except (TypeError, ValueError):
                                        placeholder_value = str(predicted)
                                input_col, status_col = st.columns([3, 1])
                                with input_col:
                                            # disable inputs for grades after the selected current grade
                                            disable_input = False
                                            try:
                                                # current slot index for this rendered group
                                                this_idx = None
                                                for idx_slot, (g, s) in enumerate(ordered_slots):
                                                    if g == grade and s == semester:
                                                        this_idx = idx_slot
                                                        break
                                                if selected_idx is not None and this_idx is not None and this_idx > selected_idx:
                                                    disable_input = True
                                            except Exception:
                                                disable_input = False
                                            st.text_input(
                                                subject_label,
                                                key=key,
                                                placeholder=placeholder_value,
                                                disabled=disable_input,
                                            )
                                status_class = {
                                    "Thực tế": "actual",
                                    "Dự đoán": "predicted",
                                    "Chưa có": "empty",
                                }.get(status_text, "empty")
                                with status_col:
                                    status_col.markdown(
                                        f"<div class='score-status'><span class='score-badge {status_class}'>{status_text}</span></div>",
                                        unsafe_allow_html=True,
                                    )
                                st.session_state.study_form_values[key] = st.session_state.get(key, "")
                        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
            
            col_back, col_skip, col_save = st.columns([1, 1, 1])
            
            with col_back:
                if st.button("⬅️ Trở lại", use_container_width=True, key="scores_back"):
                    st.session_state.first_time_step = "profile"
                    st.rerun()
            
            with col_skip:
                pass

            with col_save:
                # Allow saving when the user has selected a current grade even if no scores were entered
                save_enabled = (selected_grade is not None)
                if st.button("💾 Lưu và hoàn tất", type="primary", use_container_width=True, disabled=not save_enabled, key="scores_save"):
                    updates = []
                    deletes = []
                    has_error = False
                    for item in scores:
                        key = item["key"]
                        raw_value = str(st.session_state.get(key, "")).strip()
                        # determine index for this record so we can skip future-grade slots
                        try:
                            rec_idx = None
                            for idx_slot, (g, s) in enumerate(ordered_slots):
                                if g == item["grade_level"] and s == item["semester"]:
                                    rec_idx = idx_slot
                                    break
                        except Exception:
                            rec_idx = None

                        if raw_value == "":
                            # If the field is empty but there was an actual value stored previously,
                            # and it's within the allowed range, add to deletes.
                            if item.get("actual") is not None:
                                if not (selected_idx is not None and rec_idx is not None and rec_idx > selected_idx):
                                    deletes.append({
                                        "subject": item["subject"],
                                        "grade_level": item["grade_level"],
                                        "semester": item["semester"],
                                    })
                            continue
                        try:
                            normalized = round(float(raw_value.replace(",", ".")), 1)
                            if normalized < 0 or normalized > 10:
                                st.error(f"Điểm phải từ 0 đến 10 cho {item['subject']} ({item['semester']}/{item['grade_level']}).")
                                has_error = True
                                break
                        except ValueError:
                            st.error(f"Điểm không hợp lệ cho {item['subject']} ({item['semester']}/{item['grade_level']}).")
                            has_error = True
                            break

                        if selected_idx is not None and rec_idx is not None and rec_idx > selected_idx:
                            # skip saving scores for future grades beyond selected current grade
                            continue

                        updates.append({
                            "subject": item["subject"],
                            "grade_level": item["grade_level"],
                            "semester": item["semester"],
                            "score": normalized,
                        })
                        st.session_state.study_form_values[key] = f"{normalized:.1f}"

                    if has_error:
                        # stop early on validation errors
                        return

                    # Proceed even if there are no score updates/deletes, as long as a grade was selected
                    session = get_api_session()
                    # Update local session and user's current grade on profile before posting scores
                    st.session_state.profile["current_grade"] = selected_grade
                    try:
                        session.post(f"{API_URL}/auth/profile", json={"current_grade": selected_grade}, timeout=10)
                    except Exception:
                        pass

                    # Send updates if any (deletions now handled via inline delete buttons on Study Update page)
                    if updates:
                        try:
                            res = session.post(f"{API_URL}/study/scores/bulk", json={"scores": updates}, timeout=15)
                            if res.status_code == 200:
                                st.success("✅ Đã cập nhật điểm học tập thành công!")
                            else:
                                st.error(res.json().get("detail", "Không thể lưu dữ liệu."))
                        except requests.RequestException as exc:
                            st.error(f"Lỗi kết nối khi lưu dữ liệu: {exc}")

                    # Mark onboarding completed on server (user finished first-time flow)
                    try:
                        session.post(f"{API_URL}/auth/complete-first-time", timeout=5)
                    except Exception:
                        pass

                    # Fetch fresh study scores from server to refresh the form/UI
                    try:
                        fresh = session.get(f"{API_URL}/study/scores", timeout=10)
                        if fresh.status_code == 200:
                            data = fresh.json()
                            new_scores = data.get("scores", [])
                            # Update session state study_form_values to reflect server truth
                            st.session_state.study_form_values = {}
                            for itm in new_scores:
                                k = itm.get("key")
                                val = itm.get("actual") if itm.get("actual") is not None else itm.get("predicted")
                                if val is None:
                                    st.session_state.study_form_values[k] = ""
                                else:
                                    try:
                                        st.session_state.study_form_values[k] = f"{float(val):.1f}"
                                    except Exception:
                                        st.session_state.study_form_values[k] = str(val)
                    except requests.RequestException:
                        pass

                    # Finish onboarding locally and navigate away
                    st.session_state.first_time_step = None
                    st.session_state.is_first_login = False
                    st.balloons()
                    set_route("chat")


# =============== Chatbot with Sessions ===============
def ensure_chat_session():
    # Create an in-memory draft session if none exists. Draft sessions are not persisted
    # to the backend until the user sends the first message in that session.
    if not st.session_state.current_session_id:
        import uuid
        sid = f"draft-{uuid.uuid4().hex[:8]}"
        title = "Phiên nháp"
        st.session_state.chat_sessions.setdefault(sid, {"title": title, "messages": [], "persisted": False})
        st.session_state.current_session_id = sid


def render_chatbot():
    ensure_chat_session()
    # Helper: fetch server sessions for authenticated user
    def fetch_server_sessions():
        if not st.session_state.get("user"):
            return
        session = get_api_session()
        try:
            res = session.get(f"{API_URL}/chatbot/sessions", timeout=5)
            if res.status_code == 200:
                items = res.json()
                # merge server sessions into client sessions and remove persisted sessions
                server_ids = set()
                for it in items:
                    sid = str(it.get("id"))
                    server_ids.add(sid)
                    title = it.get("title") or f"Phiên {sid[-4:]}"
                    if sid not in st.session_state.chat_sessions:
                        st.session_state.chat_sessions[sid] = {"title": title, "messages": [], "persisted": True}
                    else:
                        # update title/persisted flag
                        st.session_state.chat_sessions[sid]["title"] = title
                        st.session_state.chat_sessions[sid]["persisted"] = True

                # remove any persisted sessions that no longer exist on server
                to_remove = []
                for k, v in list(st.session_state.chat_sessions.items()):
                    if str(k).startswith("draft-"):
                        continue
                    if v.get("persisted") and str(k) not in server_ids:
                        to_remove.append(k)
                for k in to_remove:
                    # if currently viewing this session, switch to a draft
                    try:
                        if st.session_state.current_session_id == k:
                            # remove the persisted session and create/ensure a draft
                            st.session_state.chat_sessions.pop(k, None)
                            # ensure a draft exists
                            drafts = [kk for kk in st.session_state.chat_sessions.keys() if str(kk).startswith("draft-")]
                            if drafts:
                                st.session_state.current_session_id = drafts[0]
                            else:
                                import uuid
                                new_draft = f"draft-{uuid.uuid4().hex[:8]}"
                                st.session_state.chat_sessions[new_draft] = {"title": "Phiên nháp", "messages": [], "persisted": False}
                                st.session_state.current_session_id = new_draft
                        else:
                            st.session_state.chat_sessions.pop(k, None)
                    except Exception:
                        st.session_state.chat_sessions.pop(k, None)
        except Exception:
            pass

    # Try to synchronize sessions from server when possible
    try:
        fetch_server_sessions()
    except Exception:
        pass
    with st.sidebar:
        st.header("💬 Phiên trò chuyện")
        if st.button("➕ Tạo phiên mới", use_container_width=True):
            # If a draft already exists, switch to it instead of creating a new one
            drafts = [k for k in st.session_state.chat_sessions.keys() if str(k).startswith("draft-")]
            if drafts:
                st.session_state.current_session_id = drafts[0]
            else:
                import uuid
                sid = f"draft-{uuid.uuid4().hex[:8]}"
                st.session_state.chat_sessions[sid] = {"title": "Phiên nháp", "messages": [], "persisted": False}
                st.session_state.current_session_id = sid
            st.rerun()
        if st.button("🗂️ Quản lý phiên", use_container_width=True):
            set_route("sessions", remember_prev=True)
        
        # Render sessions list (merge of persisted server sessions and local drafts)
        for sid, sess in list(sorted(st.session_state.chat_sessions.items())):
            title = sess.get("title") or ""
            # truncate long titles to keep UI compact (20 chars)
            max_len = 20
            if len(title) > max_len:
                display_title = title[: max_len - 3] + "..."
            else:
                display_title = title
            if st.button(display_title, key=f"sess_{sid}", use_container_width=True):
                # If opening a persisted server session while an empty draft exists, drop the draft
                # detect any draft with no messages
                drafts = [k for k, v in st.session_state.chat_sessions.items() if str(k).startswith("draft-")]
                for d in drafts:
                    if d != sid:
                        dv = st.session_state.chat_sessions.get(d, {})
                        if not dv.get("messages"):
                            # remove empty draft
                            st.session_state.chat_sessions.pop(d, None)
                # If selecting a persisted session, fetch its messages from server
                if st.session_state.get("user") and not str(sid).startswith("draft-"):
                    session = get_api_session()
                    try:
                        res = session.get(f"{API_URL}/chatbot/sessions/{sid}/messages", timeout=5)
                        if res.status_code == 200:
                            data = res.json()
                            msgs = data.get("messages", [])
                            st.session_state.chat_sessions[sid]["messages"] = msgs
                            st.session_state.chat_sessions[sid]["persisted"] = True
                    except Exception:
                        pass
                st.session_state.current_session_id = sid
                st.rerun()

        st.markdown("---")
        if st.button("📚 Cập nhật thông tin học tập", use_container_width=True):
            set_route("study", remember_prev=True)

    st.title("Chatbot kết nối LLM")

    pending_update = st.session_state.get("pending_score_update")
    if pending_update:
        grade_label = STUDY_GRADE_DISPLAY.get(pending_update.get("grade_level"), pending_update.get("grade_level"))
        semester_label = STUDY_SEMESTER_DISPLAY.get(pending_update.get("semester"), pending_update.get("semester"))
        current_score = pending_update.get("current_score")
        detected_old = pending_update.get("detected_old_score")
        old_display_value = detected_old if detected_old is not None else current_score
        new_display_value = pending_update.get("suggested_score")
        def _fmt(value):
            if value is None:
                return "?"
            try:
                return f"{float(value):.2f}"
            except (TypeError, ValueError):
                return str(value)
        old_display = _fmt(old_display_value)
        new_display = _fmt(new_display_value)
        st.markdown(
            f"""
            <div style="background-color:#ffe0ef;padding:16px;border-radius:10px;margin-bottom:16px;border:1px solid #f5aec7;">
                <strong>📌 Có vẻ điểm của bạn vừa thay đổi:</strong><br>
                Môn <b>{pending_update.get("subject")}</b> - {grade_label} / {semester_label}<br>
                {f"Từ <b>{old_display}</b> " if old_display_value is not None else ""}→ <b>{new_display}</b><br>
                Xác nhận cập nhật vào cơ sở dữ liệu?
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_confirm, col_dismiss = st.columns([1, 1])
        with col_confirm:
            if st.button("✅ Xác nhận cập nhật", use_container_width=True, key="confirm_pending_score"):
                session = get_api_session()
                try:
                    res = session.post(
                        f"{API_URL}/chatbot/confirm-score-update",
                        json={
                            "score_id": pending_update.get("score_id"),
                            "new_score": pending_update.get("suggested_score"),
                        },
                        timeout=20,
                    )
                    if res.status_code == 200:
                        st.success("Đã cập nhật điểm học tập thành công!")
                        st.session_state.pending_score_update = None
                        st.rerun()
                    else:
                        detail = (
                            res.json().get("detail")
                            if res.headers.get("Content-Type") == "application/json"
                            else res.text
                        )
                        st.error(f"Không thể cập nhật điểm: {detail}")
                except requests.RequestException as exc:
                    st.error(f"Lỗi kết nối khi cập nhật điểm: {exc}")
        with col_dismiss:
            if st.button("❌ Bỏ qua", use_container_width=True, key="dismiss_pending_score"):
                st.session_state.pending_score_update = None
                st.rerun()

    current = st.session_state.chat_sessions[st.session_state.current_session_id]
    msgs = current["messages"]

    # Hiển thị lịch sử
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        with st.chat_message("assistant" if role == "assistant" else "user"):
            st.write(content)
            # intentionally hide 'contexts' (nguồn tham chiếu) from assistant messages

    # Ô nhập
    prompt = st.chat_input("Nhập tin nhắn...")
    if prompt:
        # append user message immediately and set a pending_request so UI can show it
        msgs.append({"role": "user", "content": prompt})
        st.session_state.pending_score_update = None

        # Persist draft session first on next render by storing pending_request
        st.session_state.pending_request = {
            "message": prompt,
            "timestamp": datetime.utcnow().isoformat()
        }

        # ensure messages persisted in session_state
        st.session_state.chat_sessions[st.session_state.current_session_id]["messages"] = msgs
        # trigger a rerun so the user message appears immediately
        st.rerun()

    # If there's a pending request, perform the backend call while showing a loading indicator
    if st.session_state.get("pending_request"):
        pending = st.session_state.get("pending_request")
        # show a loading spinner on assistant side while waiting
        with st.spinner("Đang chờ phản hồi từ mô hình..."):
            try:
                session = get_api_session()
                cur_sid = st.session_state.current_session_id
                cur_obj = st.session_state.chat_sessions.get(cur_sid, {})

                # Build payload: if current session is a persisted server session include its id,
                # otherwise send message only and let backend auto-create the ChatSession for authenticated users.
                payload = {"message": pending.get("message")}
                # If frontend knows the logged-in user, include client_user_id as a hint
                if st.session_state.get("user"):
                    try:
                        payload["client_user_id"] = st.session_state.user.get("user_id")
                    except Exception:
                        pass
                if cur_obj.get("persisted") and not str(cur_sid).startswith("draft-"):
                    payload["session_id"] = cur_sid
                resp = session.post(f"{API_URL}/chatbot", json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    ans = data.get("answer") or data.get("response") or "(Không có phản hồi từ chatbot.)"
                    # append assistant message (do not include contexts)
                    st.session_state.chat_sessions[st.session_state.current_session_id]["messages"].append({"role": "assistant", "content": ans})
                    # handle pending profile updates / memory_saved
                    pending_score = data.get("pending_score_update")
                    if pending_score:
                        st.session_state.pending_score_update = pending_score
                    else:
                        st.session_state.pending_score_update = None
                        pending_prof = data.get("pending_profile_update")
                        if pending_prof:
                            st.session_state.pending_profile_update = pending_prof
                        else:
                            st.session_state.pending_profile_update = None
                        if data.get("memory_saved"):
                            st.success("Đã ghi nhớ thông tin cá nhân (đã lưu tự động).")
                    # sync server sessions list so management shows the new session
                    try:
                        res_list = session.get(f"{API_URL}/chatbot/sessions", timeout=5)
                        if res_list.status_code == 200:
                            items = res_list.json()
                            for it in items:
                                sid = str(it.get("id"))
                                if sid not in st.session_state.chat_sessions:
                                    st.session_state.chat_sessions[sid] = {"title": it.get("title") or f"Phiên {sid[-4:]}", "messages": [], "persisted": True}
                                else:
                                    st.session_state.chat_sessions[sid]["title"] = it.get("title") or st.session_state.chat_sessions[sid].get("title")
                    except Exception:
                        pass
                    # If backend returned a persisted session id for this message, migrate draft -> persisted
                    new_sid = data.get("session_id")
                    if new_sid and str(st.session_state.current_session_id).startswith("draft-"):
                        try:
                            cur_obj = st.session_state.chat_sessions.get(st.session_state.current_session_id, {})
                            new_title = cur_obj.get("title") or f"Phiên {str(new_sid)[-4:]}"
                            st.session_state.chat_sessions[new_sid] = {
                                "title": new_title,
                                "messages": cur_obj.get("messages", []).copy(),
                                "persisted": True,
                            }
                            st.session_state.chat_sessions.pop(st.session_state.current_session_id, None)
                            st.session_state.current_session_id = new_sid
                        except Exception:
                            pass
                else:
                    err = resp.text if resp is not None else "HTTP error"
                    st.session_state.chat_sessions[st.session_state.current_session_id]["messages"].append({"role": "assistant", "content": f"Lỗi chatbot ({getattr(resp, 'status_code', 'N/A')}): {err}"})
            except requests.RequestException as e:
                st.session_state.chat_sessions[st.session_state.current_session_id]["messages"].append({"role": "assistant", "content": f"Lỗi kết nối tới chatbot: {e}"})
            finally:
                # clear pending_request and rerender to show assistant response
                try:
                    del st.session_state["pending_request"]
                except Exception:
                    pass
                st.rerun()

# =============== Data Visualization Helpers ===============
def get_ordered_semester_keys():
    """Return ordered list of (grade, semester) tuples like (10, 1), (10, 2), (11, 1), ..."""
    keys = []
    for g in STUDY_GRADE_ORDER:
        for s in STUDY_SEMESTER_ORDER[g]:
            keys.append((int(g), int(s)))
    return keys

def get_semester_label(grade: int, semester: int) -> str:
    """e.g., (10, 1) -> '1/10'"""
    return f"{semester}/{grade}"

def filter_scores_up_to_grade(scores: List[Dict], current_grade: str) -> List[Dict]:
    """Keep only scores up to and including current_grade semester."""
    if not current_grade:
        return scores
    try:
        parts = current_grade.split("_")
        if len(parts) != 2:
            return scores
        current_sem, current_gr = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return scores
    
    ordered_keys = get_ordered_semester_keys()
    current_idx = None
    for idx, (g, s) in enumerate(ordered_keys):
        if g == current_gr and s == current_sem:
            current_idx = idx
            break
    
    if current_idx is None:
        return scores
    
    # Safely filter by trying to convert to int; skip items with invalid grade_level
    filtered = []
    for s in scores:
        try:
            grade_int = int(s["grade_level"])
            sem_int = int(s["semester"])
            if (grade_int, sem_int) <= (current_gr, current_sem):
                filtered.append(s)
        except (ValueError, TypeError):
            # Skip items with non-numeric grade_level or semester
            pass
    return filtered if filtered else scores  # Return filtered, or all if none matched

def build_line_chart_data(scores: List[Dict], subject_filter=None) -> tuple:
    """
    Build data for line chart: (x_labels, y_values_actual, y_values_predicted)
    subject_filter: set of subject codes to include, or None for all
    """
    import pandas as pd
    
    # Build rows for present scores (actual preferred, otherwise predicted)
    df_rows = []
    for item in scores:
        if subject_filter and item["subject"] not in subject_filter:
            continue
        try:
            actual = item.get("actual")
            predicted = item.get("predicted")
            value = actual if actual is not None else predicted
            if value is not None:
                grade_int = int(item["grade_level"])
                sem_int = int(item["semester"])
                df_rows.append({"grade": grade_int, "semester": sem_int, "value": float(value)})
        except (ValueError, TypeError):
            continue

    # Build ordered semester slots
    ordered_keys = get_ordered_semester_keys()
    if not ordered_keys:
        return [], [], []

    # Aggregate available values by (grade, semester)
    if df_rows:
        df = pd.DataFrame(df_rows)
        grouped = df.groupby(["grade", "semester"])['value'].mean().to_dict()
    else:
        grouped = {}

    # Build x labels and y values for the full ordered timeline
    x_labels = []
    y_values = []
    for (g, s) in ordered_keys:
        x_labels.append(get_semester_label(g, s))
        val = grouped.get((g, s))
        # use None for missing values so Plotly will break the line appropriately
        y_values.append(float(val) if val is not None else None)

    return x_labels, y_values, y_values

def build_radar_chart_data(scores: List[Dict]) -> tuple:
    """Build radar chart: (subject_names, values)"""
    import pandas as pd
    
    df_rows = []
    for item in scores:
        try:
            actual = item.get("actual")
            predicted = item.get("predicted")
            value = actual if actual is not None else predicted
            if value is not None:
                df_rows.append({
                    "subject": get_subject_display_name(item["subject"]),
                    "value": value
                })
        except (ValueError, TypeError):
            continue
    
    if not df_rows:
        return [], []
    
    df = pd.DataFrame(df_rows)
    grouped = df.groupby("subject")["value"].mean().sort_values(ascending=False)
    
    return list(grouped.index), list(grouped.values)

def build_bar_chart_data(scores: List[Dict], subject_filter=None) -> tuple:
    """Build bar chart data: (subject_names, values) aggregated by subject from filtered scores"""
    import pandas as pd
    
    df_rows = []
    for item in scores:
        if subject_filter and item["subject"] not in subject_filter:
            continue
        try:
            actual = item.get("actual")
            predicted = item.get("predicted")
            value = actual if actual is not None else predicted
            if value is not None:
                df_rows.append({
                    "subject": get_subject_display_name(item["subject"]),
                    "value": float(value)
                })
        except (ValueError, TypeError):
            continue
    
    if not df_rows:
        return [], []
    
    df = pd.DataFrame(df_rows)
    grouped = df.groupby("subject")["value"].mean().sort_values(ascending=False)
    
    return list(grouped.index), list(grouped.values)

# =============== Data Visualization ===============
def render_data_viz():
    try:
        import importlib
        go = importlib.import_module("plotly.graph_objects")
    except Exception:
        go = None
    # pandas is required for data processing; import locally to avoid unnecessary imports when not using plotting
    import pandas as pd
    
    # Professional styling
    st.set_page_config(layout="wide")
    if go is None:
        st.error("Plotly không được cài đặt trên môi trường này. Vui lòng cài đặt bằng `pip install plotly` để xem biểu đồ nâng cao.")
        return
    
    # Custom CSS for professional look
    st.markdown("""
    <style>
        .viz-header {
            padding: 0 0 20px 0;
            border-bottom: 2px solid #f0f0f0;
            margin-bottom: 20px;
        }
        .viz-title {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a1a;
            margin: 0;
        }
        .controls-row {
            display: flex;
            gap: 8px;
            margin-bottom: 25px;
            flex-wrap: wrap;
            align-items: center;
        }
        .slide-btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
            background: #f8f8f8;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
            font-weight: 500;
        }
        .slide-btn:hover {
            background: #e8e8e8;
            border-color: #d0d0d0;
        }
        .slide-btn.active {
            background: #1f77b4;
            color: white;
            border-color: #1f77b4;
        }
        .chart-container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 0 0 20px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
            margin: 0 0 15px 0;
        }
        .no-data {
            padding: 30px;
            text-align: center;
            color: #666;
            background: #f9f9f9;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class='viz-header'>
        <h1 class='viz-title'>📊 Trực Quan Dữ Liệu Học Tập</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("---")
        if st.button("📚 Cập nhật thông tin học tập", use_container_width=True):
            set_route("study", remember_prev=True)
    
    # Fetch data
    data, error = fetch_study_scores()
    if error:
        st.error(f"❌ Không thể tải dữ liệu: {error}")
        return

    scores = data.get("scores", [])
    if not scores:
        st.info("📝 Chưa có điểm số. Hãy cập nhật thông tin học tập trước.")
        return

    # Prepare score sets
    current_grade = st.session_state.get('profile', {}).get('current_grade', '')
    # `filtered_past` is used for radar (only data from current grade backwards)
    filtered_past = filter_scores_up_to_grade(scores, current_grade)
    # `full_scores` keeps the entire timeline (used for line charts so we can split into two colored segments)
    full_scores = scores

    # Slide selector and download
    slides = ["Chung", "Khối XH", "Khối TN", "Từng Khối Thi", "Từng Môn"]
    if "data_viz_slide" not in st.session_state:
        st.session_state.data_viz_slide = "Chung"

    # Controls row
    col_buttons = st.columns([1.5, 1.5, 1.5, 1.8, 1.5, 1.2])
    for i, s in enumerate(slides):
        with col_buttons[i]:
            btn_class = "active" if st.session_state.data_viz_slide == s else ""
            if st.button(s, key=f"slide_btn_{s}", use_container_width=True):
                st.session_state.data_viz_slide = s
                st.rerun()
    
    # Download button in last column
    with col_buttons[-1]:
        user = st.session_state.get("user", {})
        profile = st.session_state.get("profile", {})
        info_lines = [
            f"Họ Tên: {user.get('full_name','N/A')}",
            f"Email: {user.get('email','N/A')}",
            f"SĐT: {user.get('phone','N/A')}",
            f"Địa chỉ: {user.get('address','N/A')}",
            f"Tuổi: {user.get('age','N/A')}",
            f"Học kỳ hiện tại: {profile.get('current_grade','N/A')}",
        ]
        payload = "\n".join(info_lines)
        
    st.markdown("---")

    # Load slide comments if available
    if "slide_comments" not in st.session_state:
        st.session_state.slide_comments = {}

    # Generate slide comments button
    col_gen, col_refresh = st.columns([1, 1])
    with col_gen:
        if st.button("💬 Sinh nhận xét từ AI", use_container_width=True, key="gen_comments"):
            session = get_api_session()
            try:
                res = session.post(f"{API_URL}/study/generate-slide-comments", timeout=120)
                if res.status_code == 200:
                    comments_data = res.json()
                    st.session_state.slide_comments = comments_data.get("slide_comments", {})
                    st.success("✅ Đã sinh nhận xét cho tất cả slide")
                    st.rerun()
                else:
                    st.error(f"Lỗi sinh nhận xét: {res.json().get('detail', res.text)}")
            except requests.RequestException as e:
                st.error(f"Lỗi kết nối: {e}")
    with col_refresh:
        if st.button("🔄 Làm mới", use_container_width=True, key="refresh_data"):
            st.rerun()

    st.markdown("---")    # Render slide content
    slide = st.session_state.data_viz_slide
    
    if slide == "Chung":
        st.markdown("<div class='chart-container'><h2 class='chart-title'>📈 Tổng Quan Chung</h2>", unsafe_allow_html=True)
        
        # Display AI comment for this slide
        if slide in st.session_state.slide_comments:
            comment = st.session_state.slide_comments[slide]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>💬 Nhận xét từ AI:</strong><br>{comment}
            </div>
            """, unsafe_allow_html=True)
        
        # Line chart (use full timeline and split into two colored segments)
        x_labels, y_values, _ = build_line_chart_data(full_scores)
        if x_labels and len(y_values) > 0:
            try:
                split_idx = len(x_labels)
                if current_grade:
                    parts = current_grade.split("_")
                    if len(parts) == 2:
                        current_sem, current_gr = int(parts[0]), int(parts[1])
                        ordered_keys = get_ordered_semester_keys()
                        for idx, (g, s) in enumerate(ordered_keys):
                            if g == current_gr and s == current_sem:
                                # include up to "after current grade 2 học kỳ".
                                # Example: current=1/11 -> include through 1/12 (idx + 3)
                                split_idx = min(idx + 3, len(x_labels))
                                break
                
                fig = go.Figure()
                seg_x = x_labels[:split_idx]
                seg_y = y_values[:split_idx]
                text_vals = [f"{v:.1f}" if (v is not None) else "" for v in seg_y]
                fig.add_trace(go.Scatter(
                    x=seg_x,
                    y=seg_y,
                    mode='lines+markers+text',
                    name='Điểm thực tế (xanh)',
                    line=dict(color='#27ae60', width=3.5),
                    marker=dict(size=9, color='#27ae60'),
                    text=text_vals,
                    textposition='top center',
                    textfont=dict(size=13, color='#27ae60', family='Arial Black'),
                    hovertemplate='<b>%{x}</b><br>Điểm: %{y:.1f}<extra></extra>'
                ))
                if split_idx < len(x_labels):
                    seg2_x = x_labels[split_idx-1:]
                    seg2_y = y_values[split_idx-1:]
                    text_vals2 = [f"{v:.1f}" if (v is not None) else "" for v in seg2_y]
                    fig.add_trace(go.Scatter(
                        x=seg2_x,
                        y=seg2_y,
                        mode='lines+markers+text',
                        name='Dự báo (đỏ)',
                        line=dict(color='#e74c3c', width=3.5, dash='dash'),
                        marker=dict(size=9, color='#e74c3c'),
                        text=text_vals2,
                        textposition='bottom center',
                        textfont=dict(size=13, color='#e74c3c', family='Arial Black'),
                        hovertemplate='<b>%{x}</b><br>Dự báo: %{y:.1f}<extra></extra>'
                    ))
                
                fig.update_layout(
                    title=None,
                    xaxis_title="Học kỳ",
                    yaxis_title="Điểm (0-10)",
                    hovermode='x unified',
                    height=480,
                    template='plotly_white',
                    font=dict(family="Arial, sans-serif", size=13),
                    xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=12)),
                    yaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', range=[0, 10], tickfont=dict(size=12)),
                    legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)', bordercolor='#ddd', borderwidth=1),
                    margin=dict(t=20)
                )
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ: {str(e)}")
        else:
            st.markdown("<div class='no-data'>Không có dữ liệu để hiển thị biểu đồ</div>", unsafe_allow_html=True)
        
        # Bar chart: average score by subject (use filtered_past data)
        st.markdown("<h3 class='chart-title' style='margin-top: 30px; margin-bottom: 15px;'>📊 Điểm Trung Bình Từng Môn</h3>", unsafe_allow_html=True)
        subjects, values = build_bar_chart_data(filtered_past)
        if subjects and len(values) > 0:
            try:
                fig_bar = go.Figure(data=[go.Bar(
                    x=subjects,
                    y=values,
                    text=[f"{v:.1f}" for v in values],
                    textposition='outside',
                    textfont=dict(size=12, family='Arial Black'),
                    marker=dict(color='#3498db', line=dict(color='#2980b9', width=2)),
                    hovertemplate='<b>%{x}</b><br>Điểm TB: %{y:.1f}<extra></extra>'
                )])
                fig_bar.update_layout(
                    title=None,
                    xaxis_title="Môn học",
                    yaxis_title="Điểm (0-10)",
                    height=380,
                    template='plotly_white',
                    font=dict(family="Arial, sans-serif", size=12),
                    xaxis=dict(tickangle=-15, tickfont=dict(size=11)),
                    yaxis=dict(range=[0, 10], tickfont=dict(size=11)),
                    showlegend=False,
                    margin=dict(b=100, t=20)
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ cột: {str(e)}")
        else:
            st.markdown("<div class='no-data'>Không có dữ liệu để hiển thị biểu đồ cột</div>", unsafe_allow_html=True)
        
        # Radar chart (only use data up to current grade)
        st.markdown("<h3 class='chart-title' style='margin-top: 30px; margin-bottom: 15px;'>🎯 Đánh Giá Từng Môn</h3>", unsafe_allow_html=True)
        subjects, values = build_radar_chart_data(filtered_past)
        if subjects and len(values) > 0:
            try:
                fig_radar = go.Figure(data=go.Scatterpolar(
                    r=values,
                    theta=subjects,
                    fill='toself',
                    name='Điểm TB',
                    line=dict(color='#3498db', width=2.5),
                    fillcolor='rgba(52, 152, 219, 0.3)',
                    text=[f"{v:.1f}" for v in values],
                    textposition='top center',
                    textfont=dict(size=12, color='#1c5aa5', family='Arial Black'),
                    hovertemplate='<b>%{theta}</b><br>Điểm: %{r:.1f}<extra></extra>'
                ))
                fig_radar.update_layout(
                    title=None,
                    polar=dict(radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(size=11))),
                    height=500,
                    font=dict(family="Arial, sans-serif", size=12),
                    template='plotly_white'
                )
                st.plotly_chart(fig_radar, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ radar: {str(e)}")
        else:
            st.markdown("<div class='no-data'>Không có dữ liệu để hiển thị biểu đồ radar</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif slide == "Khối XH":
        st.markdown("<div class='chart-container'><h2 class='chart-title'>📚 Khối Xã Hội (Toán, Văn, Anh, Sử, Địa, CD)</h2>", unsafe_allow_html=True)
        
        # Display AI comment for this slide
        if slide in st.session_state.slide_comments:
            comment = st.session_state.slide_comments[slide]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>💬 Nhận xét từ AI:</strong><br>{comment}
            </div>
            """, unsafe_allow_html=True)
        
        filtered_by_subject = [s for s in full_scores if s["subject"] in KHOI_XH_SUBJECTS]
        x_labels, y_values, _ = build_line_chart_data(filtered_by_subject)
        if x_labels and len(y_values) > 0:
            try:
                # compute split index same as in Chung
                split_idx = len(x_labels)
                if current_grade:
                    parts = current_grade.split("_")
                    if len(parts) == 2:
                        current_sem, current_gr = int(parts[0]), int(parts[1])
                        ordered_keys = get_ordered_semester_keys()
                        for idx, (g, s) in enumerate(ordered_keys):
                            if g == current_gr and s == current_sem:
                                split_idx = min(idx + 3, len(x_labels))
                                break
                fig = go.Figure()
                seg_x = x_labels[:split_idx]
                seg_y = y_values[:split_idx]
                text_vals = [f"{v:.1f}" if (v is not None) else "" for v in seg_y]
                fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode='lines+markers+text', name='Khối XH (xanh)',
                                        line=dict(color='#27ae60', width=3.5), marker=dict(size=9, color='#27ae60'),
                                        text=text_vals, textposition='top center', textfont=dict(size=13, color='#27ae60', family='Arial Black')))
                if split_idx < len(x_labels):
                    seg2_x = x_labels[split_idx-1:]
                    seg2_y = y_values[split_idx-1:]
                    text_vals2 = [f"{v:.1f}" if (v is not None) else "" for v in seg2_y]
                    fig.add_trace(go.Scatter(x=seg2_x, y=seg2_y, mode='lines+markers+text', name='Khối XH (đỏ)',
                                            line=dict(color='#e74c3c', width=3.5, dash='dash'), marker=dict(size=9, color='#e74c3c'),
                                            text=text_vals2, textposition='bottom center', textfont=dict(size=13, color='#e74c3c', family='Arial Black')))
                fig.update_layout(title=None, xaxis_title="Học kỳ", yaxis_title="Điểm (0-10)",
                                height=480, template='plotly_white', hovermode='x unified',
                                font=dict(family="Arial, sans-serif", size=13),
                                xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=12)),
                                yaxis=dict(range=[0, 10], showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=12)),
                                legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)', bordercolor='#ddd', borderwidth=1),
                                margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ Khối XH: {str(e)}")
        
        # Bar chart for Khối XH (use filtered_past data)
        st.markdown("<h3 class='chart-title' style='margin-top: 30px; margin-bottom: 15px;'>📊 Điểm Trung Bình Từng Môn (Khối XH)</h3>", unsafe_allow_html=True)
        filtered_past_xh = [s for s in filtered_past if s["subject"] in KHOI_XH_SUBJECTS]
        subjects, values = build_bar_chart_data(filtered_past_xh)
        if subjects and len(values) > 0:
            try:
                fig_bar = go.Figure(data=[go.Bar(
                    x=subjects,
                    y=values,
                    text=[f"{v:.1f}" for v in values],
                    textposition='outside',
                    textfont=dict(size=12, family='Arial Black'),
                    marker=dict(color='#27ae60', line=dict(color='#1e8449', width=2)),
                    hovertemplate='<b>%{x}</b><br>Điểm TB: %{y:.1f}<extra></extra>'
                )])
                fig_bar.update_layout(
                    title=None,
                    xaxis_title="Môn học",
                    yaxis_title="Điểm (0-10)",
                    height=380,
                    template='plotly_white',
                    font=dict(family="Arial, sans-serif", size=12),
                    xaxis=dict(tickangle=-15, tickfont=dict(size=11)),
                    yaxis=dict(range=[0, 10], tickfont=dict(size=11)),
                    showlegend=False,
                    margin=dict(b=100, t=20)
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ cột: {str(e)}")
        else:
            st.markdown("<div class='no-data'>Không có dữ liệu để hiển thị biểu đồ cột</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif slide == "Khối TN":
        st.markdown("<div class='chart-container'><h2 class='chart-title'>🔬 Khối Tự Nhiên (Toán, Văn, Anh, Lý, Hóa, Sinh)</h2>", unsafe_allow_html=True)
        
        # Display AI comment for this slide
        if slide in st.session_state.slide_comments:
            comment = st.session_state.slide_comments[slide]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>💬 Nhận xét từ AI:</strong><br>{comment}
            </div>
            """, unsafe_allow_html=True)
        
        filtered_by_subject = [s for s in full_scores if s["subject"] in KHOI_TN_SUBJECTS]
        x_labels, y_values, _ = build_line_chart_data(filtered_by_subject)
        if x_labels and len(y_values) > 0:
            try:
                split_idx = len(x_labels)
                if current_grade:
                    parts = current_grade.split("_")
                    if len(parts) == 2:
                        current_sem, current_gr = int(parts[0]), int(parts[1])
                        ordered_keys = get_ordered_semester_keys()
                        for idx, (g, s) in enumerate(ordered_keys):
                            if g == current_gr and s == current_sem:
                                split_idx = min(idx + 3, len(x_labels))
                                break
                fig = go.Figure()
                seg_x = x_labels[:split_idx]
                seg_y = y_values[:split_idx]
                text_vals = [f"{v:.1f}" if (v is not None) else "" for v in seg_y]
                fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode='lines+markers+text', name='Khối TN (tím)',
                                        line=dict(color='#9b59b6', width=3.5), marker=dict(size=9, color='#9b59b6'),
                                        text=text_vals, textposition='top center', textfont=dict(size=13, color='#9b59b6', family='Arial Black')))
                if split_idx < len(x_labels):
                    seg2_x = x_labels[split_idx-1:]
                    seg2_y = y_values[split_idx-1:]
                    text_vals2 = [f"{v:.1f}" if (v is not None) else "" for v in seg2_y]
                    fig.add_trace(go.Scatter(x=seg2_x, y=seg2_y, mode='lines+markers+text', name='Khối TN (đỏ)',
                                            line=dict(color='#e74c3c', width=3.5, dash='dash'), marker=dict(size=9, color='#e74c3c'),
                                            text=text_vals2, textposition='bottom center', textfont=dict(size=13, color='#e74c3c', family='Arial Black')))
                fig.update_layout(title=None, xaxis_title="Học kỳ", yaxis_title="Điểm (0-10)",
                                height=480, template='plotly_white', hovermode='x unified',
                                font=dict(family="Arial, sans-serif", size=13),
                                xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=12)),
                                yaxis=dict(range=[0, 10], showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=12)),
                                legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)', bordercolor='#ddd', borderwidth=1),
                                margin=dict(t=20))
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ Khối TN: {str(e)}")
        else:
            st.markdown("<div class='no-data'>Không có dữ liệu cho Khối TN</div>", unsafe_allow_html=True)
        
        # Bar chart for Khối TN (use filtered_past data)
        st.markdown("<h3 class='chart-title' style='margin-top: 30px; margin-bottom: 15px;'>📊 Điểm Trung Bình Từng Môn (Khối TN)</h3>", unsafe_allow_html=True)
        filtered_past_tn = [s for s in filtered_past if s["subject"] in KHOI_TN_SUBJECTS]
        subjects, values = build_bar_chart_data(filtered_past_tn)
        if subjects and len(values) > 0:
            try:
                fig_bar = go.Figure(data=[go.Bar(
                    x=subjects,
                    y=values,
                    text=[f"{v:.1f}" for v in values],
                    textposition='outside',
                    textfont=dict(size=12, family='Arial Black'),
                    marker=dict(color='#9b59b6', line=dict(color='#6c3a7d', width=2)),
                    hovertemplate='<b>%{x}</b><br>Điểm TB: %{y:.1f}<extra></extra>'
                )])
                fig_bar.update_layout(
                    title=None,
                    xaxis_title="Môn học",
                    yaxis_title="Điểm (0-10)",
                    height=380,
                    template='plotly_white',
                    font=dict(family="Arial, sans-serif", size=12),
                    xaxis=dict(tickangle=-15, tickfont=dict(size=11)),
                    yaxis=dict(range=[0, 10], tickfont=dict(size=11)),
                    showlegend=False,
                    margin=dict(b=100, t=20)
                )
                st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
            except Exception as e:
                st.error(f"Lỗi vẽ biểu đồ cột: {str(e)}")
        else:
            st.markdown("<div class='no-data'>Không có dữ liệu để hiển thị biểu đồ cột</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    elif slide == "Từng Khối Thi":
        st.markdown("<div class='chart-container'><h2 class='chart-title'>🎯 Từng Khối Thi</h2></div>", unsafe_allow_html=True)
        
        # Display AI comment for this slide
        if slide in st.session_state.slide_comments:
            comment = st.session_state.slide_comments[slide]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>💬 Nhận xét từ AI:</strong><br>{comment}
            </div>
            """, unsafe_allow_html=True)
        
        cols = st.columns(2)
        block_names = ["A00", "B00", "C00", "D01"]
        colors = {"A00": "#e74c3c", "B00": "#f39c12", "C00": "#16a085", "D01": "#8e44ad"}
        color_map = {"A00": "#c0392b", "B00": "#d68910", "C00": "#117a65", "D01": "#6c3483"}  # darker for bar chart
        
        for idx, block_name in enumerate(block_names):
            block_subjects = EXAM_BLOCKS[block_name]
            filtered_by_block = [s for s in full_scores if s["subject"] in block_subjects]
            x_labels, y_values, _ = build_line_chart_data(filtered_by_block)
            
            with cols[idx % 2]:
                st.markdown(f"<div class='chart-container'><h3 class='chart-title'>Khối {block_name}</h3>", unsafe_allow_html=True)
                if x_labels and len(y_values) > 0:
                    try:
                        split_idx = len(x_labels)
                        if current_grade:
                            parts = current_grade.split("_")
                            if len(parts) == 2:
                                current_sem, current_gr = int(parts[0]), int(parts[1])
                                ordered_keys = get_ordered_semester_keys()
                                for idx_k, (g, s) in enumerate(ordered_keys):
                                    if g == current_gr and s == current_sem:
                                        split_idx = min(idx_k + 3, len(x_labels))
                                        break
                        fig = go.Figure()
                        seg_x = x_labels[:split_idx]
                        seg_y = y_values[:split_idx]
                        text_vals = [f"{v:.1f}" if (v is not None) else "" for v in seg_y]
                        fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode='lines+markers+text', name=block_name,
                                                line=dict(color=colors[block_name], width=3), marker=dict(size=8, color=colors[block_name]),
                                                text=text_vals, textposition='top center', textfont=dict(size=12, color=colors[block_name], family='Arial Black')))
                        if split_idx < len(x_labels):
                            seg2_x = x_labels[split_idx-1:]
                            seg2_y = y_values[split_idx-1:]
                            text_vals2 = [f"{v:.1f}" if (v is not None) else "" for v in seg2_y]
                            fig.add_trace(go.Scatter(x=seg2_x, y=seg2_y, mode='lines+markers+text', name=f"{block_name} (dự báo)",
                                                    line=dict(color='#e74c3c', width=3, dash='dash'), marker=dict(size=8, color='#e74c3c'),
                                                    text=text_vals2, textposition='bottom center', textfont=dict(size=12, color='#e74c3c', family='Arial Black')))
                        fig.update_layout(title=None, xaxis_title="Học kỳ", yaxis_title="Điểm (0-10)",
                                        height=380, template='plotly_white', hovermode='x unified',
                                        font=dict(family="Arial, sans-serif", size=12),
                                        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=11)),
                                        yaxis=dict(range=[0, 10], showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=11)),
                                        legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)', bordercolor='#ddd', borderwidth=1),
                                        margin=dict(t=20))
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    except Exception as e:
                        st.error(f"Lỗi vẽ Khối {block_name}: {e}")
                    
                    # Bar chart for this exam block (use filtered_past data)
                    filtered_past_block = [s for s in filtered_past if s["subject"] in block_subjects]
                    subjects, values = build_bar_chart_data(filtered_past_block)
                    if subjects and len(values) > 0:
                        try:
                            st.markdown(f"<h4 style='margin-top: 15px; margin-bottom: 10px; font-size: 14px; color: #666;'>📊 Điểm TB Từng Môn (Khối {block_name})</h4>", unsafe_allow_html=True)
                            fig_bar = go.Figure(data=[go.Bar(
                                x=subjects,
                                y=values,
                                text=[f"{v:.1f}" for v in values],
                                textposition='outside',
                                textfont=dict(size=11, family='Arial Black'),
                                marker=dict(color=color_map[block_name], line=dict(color=colors[block_name], width=1.5)),
                                hovertemplate='<b>%{x}</b><br>Điểm TB: %{y:.1f}<extra></extra>'
                            )])
                            fig_bar.update_layout(
                                title=None,
                                xaxis_title="Môn học",
                                yaxis_title="Điểm (0-10)",
                                height=300,
                                template='plotly_white',
                                font=dict(family="Arial, sans-serif", size=11),
                                xaxis=dict(tickangle=-15, tickfont=dict(size=10)),
                                yaxis=dict(range=[0, 10], tickfont=dict(size=10)),
                                showlegend=False,
                                margin=dict(b=80, t=20)
                            )
                            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
                        except Exception as e:
                            st.error(f"Lỗi vẽ bar chart Khối {block_name}: {str(e)}")
                else:
                    st.markdown("<div class='no-data'>Không có dữ liệu</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
    
    else:  # Từng Môn
        st.markdown("<div class='chart-container'><h2 class='chart-title'>📖 Biểu Đồ Từng Môn</h2></div>", unsafe_allow_html=True)
        
        # Display AI comment for this slide
        if "Từng Môn" in st.session_state.slide_comments:
            comment = st.session_state.slide_comments["Từng Môn"]
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <strong>💬 Nhận xét từ AI:</strong><br>{comment}
            </div>
            """, unsafe_allow_html=True)
        
        cols = st.columns(3)
        colors_subjects = ["#3498db", "#e74c3c", "#f39c12", "#27ae60", "#9b59b6", "#16a085", "#c0392b", "#2980b9", "#d35400"]
        
        for idx, subject_code in enumerate(STUDY_SUBJECTS):
            filtered_by_subject = [s for s in full_scores if s["subject"] == subject_code]
            x_labels, y_values, _ = build_line_chart_data(filtered_by_subject)
            
            with cols[idx % 3]:
                subject_name = get_subject_display_name(subject_code)
                st.markdown(f"<div class='chart-container'><h3 class='chart-title'>{subject_name}</h3>", unsafe_allow_html=True)
                if x_labels and len(y_values) > 0:
                    try:
                        split_idx = len(x_labels)
                        if current_grade:
                            parts = current_grade.split("_")
                            if len(parts) == 2:
                                current_sem, current_gr = int(parts[0]), int(parts[1])
                                ordered_keys = get_ordered_semester_keys()
                                for idx_k, (g, s) in enumerate(ordered_keys):
                                    if g == current_gr and s == current_sem:
                                        split_idx = min(idx_k + 3, len(x_labels))
                                        break
                        fig = go.Figure()
                        seg_x = x_labels[:split_idx]
                        seg_y = y_values[:split_idx]
                        text_vals = [f"{v:.1f}" if (v is not None) else "" for v in seg_y]
                        color_idx = idx % len(colors_subjects)
                        fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode='lines+markers+text',
                                                name=subject_name,
                                                line=dict(color=colors_subjects[color_idx], width=2.5),
                                                marker=dict(size=7, color=colors_subjects[color_idx]),
                                                text=text_vals, textposition='top center', textfont=dict(size=11, color=colors_subjects[color_idx], family='Arial Black')))
                        if split_idx < len(x_labels):
                            seg2_x = x_labels[split_idx-1:]
                            seg2_y = y_values[split_idx-1:]
                            text_vals2 = [f"{v:.1f}" if (v is not None) else "" for v in seg2_y]
                            fig.add_trace(go.Scatter(x=seg2_x, y=seg2_y, mode='lines+markers+text',
                                                    name=f"{subject_name} (dự báo)",
                                                    line=dict(color='#e74c3c', width=2.5, dash='dash'),
                                                    marker=dict(size=7, color='#e74c3c'),
                                                    text=text_vals2, textposition='bottom center', textfont=dict(size=11, color='#e74c3c', family='Arial Black')))
                        fig.update_layout(title=None, xaxis_title="Học kỳ", yaxis_title="Điểm",
                                        height=340, template='plotly_white', hovermode='x unified',
                                        font=dict(family="Arial, sans-serif", size=11),
                                        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=10)),
                                        yaxis=dict(range=[0, 10], showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickfont=dict(size=10)),
                                        legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)', bordercolor='#ddd', borderwidth=1),
                                        margin=dict(t=20))
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    except Exception as e:
                        st.error(f"Lỗi vẽ biểu đồ cho {subject_name}: {e}")
                    
                    # Bar chart for this subject (use filtered_past data)
                    filtered_past_subject = [s for s in filtered_past if s["subject"] == subject_code]
                    subjects, values = build_bar_chart_data(filtered_past_subject)
                    if subjects and len(values) > 0:
                        try:
                            st.markdown(f"<h4 style='margin-top: 15px; margin-bottom: 10px; font-size: 12px; color: #666;'>📊 Điểm Trung Bình</h4>", unsafe_allow_html=True)
                            fig_bar = go.Figure(data=[go.Bar(
                                x=subjects,
                                y=values,
                                text=[f"{v:.1f}" for v in values],
                                textposition='outside',
                                textfont=dict(size=10, family='Arial Black'),
                                marker=dict(color=colors_subjects[idx % len(colors_subjects)], line=dict(color=colors_subjects[idx % len(colors_subjects)], width=1)),
                                hovertemplate='<b>%{x}</b><br>Điểm TB: %{y:.1f}<extra></extra>'
                            )])
                            fig_bar.update_layout(
                                title=None,
                                xaxis_title="",
                                yaxis_title="Điểm (0-10)",
                                height=280,
                                template='plotly_white',
                                font=dict(family="Arial, sans-serif", size=10),
                                xaxis=dict(tickangle=-15, tickfont=dict(size=9)),
                                yaxis=dict(range=[0, 10], tickfont=dict(size=9)),
                                showlegend=False,
                                margin=dict(b=70, t=20)
                            )
                            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
                        except Exception as e:
                            st.error(f"Lỗi vẽ bar chart cho {subject_name}: {str(e)}")
                else:
                    st.markdown("<div class='no-data'>Không có dữ liệu</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)




# =============== Developer Tools ===============
def render_developer_tools():
    st.title("Công cụ dành cho Developer")
    if st.session_state.user.get("role") not in {"developer", "admin"}:
        st.error("Bạn không có quyền truy cập vào trang này.")
        return
    st.markdown(
        """
        Import một file Excel dùng độc lập cho mô hình KNN.  
        Mỗi cột mang nhãn `Môn_Kỳ_Lớp` (ví dụ `Toán_1_10`), mỗi hàng là một mẫu chuẩn hóa.
        Sau khi tải lên, hệ thống sẽ:
        - Lưu tập tham chiếu vào bảng `knn_reference_samples`.
        - Tự động tính lại điểm dự đoán cho mọi người dùng dựa trên dataset mới.
        - Đồng bộ lại embedding phục vụ RAG.
        """
    )

    st.subheader("Import tập dữ liệu tham chiếu")
    st.caption("File gồm các cột dạng `Toán_1_10`, ...; không cần cột thông tin người dùng.")

    if st.session_state.get("last_knn_import_summary"):
        summary = st.session_state.last_knn_import_summary
        st.success(
            f"Bộ dữ liệu tham chiếu hiện tại có {summary.get('reference_samples', 0)} mẫu / {summary.get('total_rows', 0)} dòng hợp lệ."
        )
        if summary.get("cleared_existing"):
            st.info("Đã thay thế dữ liệu tham chiếu cũ.")
        if summary.get("warnings"):
            with st.expander("⚠️ Cảnh báo dữ liệu tham chiếu", expanded=False):
                for warn in summary["warnings"]:
                    st.write(f"- {warn}")
        if summary.get("errors"):
            with st.expander("❗ Lỗi dữ liệu tham chiếu", expanded=False):
                for err in summary["errors"]:
                    st.write(f"- {err}")

    with st.form("knn_import_form"):
        knn_file = st.file_uploader(
            "Chọn file Excel tập tham chiếu (.xlsx, .xls)",
            type=["xlsx", "xls"],
            accept_multiple_files=False,
            key="upload_knn_dataset",
        )
        submit_knn = st.form_submit_button("📥 Import dataset", use_container_width=True)

    if submit_knn:
        if not knn_file:
            st.error("Vui lòng chọn file Excel trước khi import.")
        else:
            file_bytes = knn_file.getvalue()
            session = get_api_session()
            try:
                files = {
                    "file": (
                        knn_file.name,
                        file_bytes,
                        knn_file.type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                }
                res = session.post(f"{API_URL}/developer/import-excel", files=files, timeout=90)
                if res.status_code == 200:
                    summary = res.json().get("summary", {})
                    st.session_state.last_knn_import_summary = summary
                    st.success(
                        f"Đã import {summary.get('reference_samples', 0)} mẫu tham chiếu từ {summary.get('total_rows', 0)} dòng."
                    )
                    if summary.get("warnings"):
                        st.warning("Một số dữ liệu bị bỏ qua. Xem chi tiết trong báo cáo.")
                    if summary.get("errors"):
                        st.error("Có lỗi trong quá trình import dữ liệu tham chiếu. Kiểm tra báo cáo.")
                    st.rerun()
                else:
                    detail = res.json().get("detail") if res.headers.get("Content-Type") == "application/json" else res.text
                    st.error(f"Import dataset tham chiếu thất bại: {detail}")
            except requests.RequestException as exc:
                st.error(f"Lỗi kết nối khi import dữ liệu tham chiếu: {exc}")

    st.markdown("---")
    if st.button("🔄 Tạo lại vector database từ dữ liệu hiện có", use_container_width=True):
        session = get_api_session()
        try:
            res = session.post(f"{API_URL}/developer/rebuild-embeddings", timeout=90)
            if res.status_code == 200:
                st.success("Đã tái xây dựng vector database.")
            else:
                detail = res.json().get("detail") if res.headers.get("Content-Type") == "application/json" else res.text
                st.error(f"Không thể tái xây dựng vector database: {detail}")
        except requests.RequestException as exc:
            st.error(f"Lỗi kết nối khi gọi backend: {exc}")


# =============== Settings ===============
def render_settings():
    st.title("Cài đặt tài khoản")
    name = st.text_input("Họ và tên", value=st.session_state.profile.get("name", ""))
    email = st.text_input("Email", value=st.session_state.profile.get("email", ""))
    phone = st.text_input("Số điện thoại", value=st.session_state.profile.get("phone", ""))
    address = st.text_input("Địa chỉ", value=st.session_state.profile.get("address", ""))
    age = st.text_input("Tuổi", value=st.session_state.profile.get("age", ""))
    # Grade selection
    grade_options = []
    grade_map = {}
    for g in STUDY_GRADE_ORDER:
        for s in STUDY_SEMESTER_ORDER[g]:
            display = f"{STUDY_SEMESTER_DISPLAY.get(s, s)} {STUDY_GRADE_DISPLAY.get(g, g)}"
            value = f"{s}_{g}"
            grade_options.append(display)
            grade_map[display] = value
    current_grade_val = st.session_state.profile.get("current_grade") if st.session_state.profile else None
    initial_display = None
    if current_grade_val:
        for disp, val in grade_map.items():
            if val == current_grade_val:
                initial_display = disp
                break
    selected_display = st.selectbox("Học kỳ hiện tại", options=grade_options, index=grade_options.index(initial_display) if initial_display in grade_options else 0)
    selected_grade = grade_map.get(selected_display)
    col1, col2, col3 = st.columns([2,1,1])
    with col1:
        if st.button("Lưu thay đổi", type="primary", use_container_width=True):
            st.session_state.profile.update({
                "name": name,
                "email": email,
                "phone": phone,
                "address": address,
                "age": age,
            })
            session = get_api_session()
            payload = {
                "email": email or None,
                "phone": phone or None,
                "address": address or None,
                "age": age or None,
                "current_grade": selected_grade or None,
            }
            try:
                res = session.post(f"{API_URL}/auth/profile", json=payload, timeout=10)
                if res.status_code in (200, 204):
                    profile_data = res.json().get("profile", {}) if res.content else {}
                    for field, value in profile_data.items():
                        st.session_state.profile[field] = value or ""
                    st.success("Đã lưu cài đặt")
                else:
                    st.error(res.json().get("detail", "Không thể lưu dữ liệu."))
            except requests.RequestException as exc:
                st.error(f"Lỗi kết nối: {exc}")
    with col2:
        if st.button("Quay lại", use_container_width=True):
            back = st.session_state.prev_route or "chat"
            set_route(back)
    with col3:
        if st.button("Đăng xuất", use_container_width=True):
            session = get_api_session()
            try:
                session.post(f"{API_URL}/auth/logout", timeout=10)
            except requests.RequestException:
                pass
            for k in ["user", "profile", "is_first_login", "chat_sessions", "current_session_id", "study_form_values", "first_time_step", "pending_score_update"]:
                if k in st.session_state:
                    del st.session_state[k]
            if "api_session" in st.session_state:
                st.session_state.api_session.close()
                del st.session_state.api_session
            st.session_state.auth_tab = "login"
            set_route("auth")


# =============== Sessions Manager Page ===============
def render_sessions_manager():
    st.title("Quản lý phiên trò chuyện")
    st.caption("Xem, đổi tên và xóa các phiên đã tồn tại.")

    # Fetch server sessions when possible
    server_sessions = None
    if st.session_state.get("user"):
        session = get_api_session()
        try:
            res = session.get(f"{API_URL}/chatbot/sessions", timeout=5)
            if res.status_code == 200:
                server_sessions = res.json()
        except Exception:
            server_sessions = None

    if not server_sessions:
        st.info("Chưa có phiên nào. Hãy tạo phiên mới trong Chatbot.")
    else:
        # Track which session is in edit mode
        if "editing_session_id" not in st.session_state:
            st.session_state.editing_session_id = None
        
        for s in server_sessions:
            sid = str(s.get("id"))
            title = s.get("title") or f"Phiên {sid[-4:]}"
            c1, c2, c3 = st.columns([4,1,1])
            with c1:
                # If this session is being edited, show input field; otherwise show title
                if st.session_state.editing_session_id == sid:
                    new_title = st.text_input("Tiêu đề mới", value=title, key=f"rename_input_{sid}")
                else:
                    # truncate long titles for compact display
                    max_len = 60
                    if title and len(title) > max_len:
                        st.write(title[: max_len - 3] + "...")
                    else:
                        st.write(title)
            with c2:
                if st.session_state.editing_session_id == sid:
                    # Show Save button when editing
                    if st.button("💾 Lưu", key=f"rename_save_{sid}"):
                        if new_title and new_title != title:
                            session = get_api_session()
                            try:
                                resp = session.put(f"{API_URL}/chatbot/sessions/{sid}", json={"title": new_title}, timeout=5)
                            except requests.RequestException:
                                st.error("Lỗi khi gọi backend.")
                            else:
                                if resp.status_code in (200, 204):
                                    st.success("Đã cập nhật tiêu đề.")
                                    st.session_state.editing_session_id = None
                                    st.rerun()
                                else:
                                    detail = resp.json().get("detail") if resp.headers.get("Content-Type") == "application/json" else resp.text
                                    st.error(f"Không thể cập nhật tiêu đề: {detail}")
                        else:
                            st.session_state.editing_session_id = None
                            st.rerun()

            with c3:
                if st.session_state.editing_session_id == sid:
                    # Show Cancel button when editing
                    if st.button("❌ Hủy", key=f"rename_cancel_{sid}"):
                        st.session_state.editing_session_id = None
                        st.rerun()
                else:
                    # Show Delete button normally
                    if st.button("🗑️ Xoá", key=f"sessions_del_{sid}"):
                        session = get_api_session()
                        try:
                            resp = session.delete(f"{API_URL}/chatbot/sessions/{sid}", timeout=5)
                        except requests.RequestException:
                            st.error("Lỗi khi gọi backend.")
                        else:
                            if resp.status_code in (200, 204):
                                st.success("Đã xóa phiên.")
                                # remove from local session cache so Chat UI updates immediately
                                try:
                                    st.session_state.chat_sessions.pop(sid, None)
                                    # if we were viewing it, switch to an existing draft or create one
                                    if st.session_state.get("current_session_id") == sid:
                                        drafts = [k for k in st.session_state.chat_sessions.keys() if str(k).startswith("draft-")]
                                        if drafts:
                                            st.session_state.current_session_id = drafts[0]
                                        else:
                                            import uuid
                                            new_draft = f"draft-{uuid.uuid4().hex[:8]}"
                                            st.session_state.chat_sessions[new_draft] = {"title": "Phiên nháp", "messages": [], "persisted": False}
                                            st.session_state.current_session_id = new_draft
                                except Exception:
                                    pass
                                st.rerun()
                            else:
                                detail = resp.json().get("detail") if resp.headers.get("Content-Type") == "application/json" else resp.text
                                st.error(f"Không thể xóa phiên: {detail}")

    st.markdown("---")
    st.subheader("Thông tin cá nhân hoá (không nhạy cảm)")
    # Fetch user preferences and allow delete
    prefs = None
    if st.session_state.get("user"):
        try:
            session = get_api_session()
            res = session.get(f"{API_URL}/user/preferences", timeout=5)
            if res.status_code == 200:
                prefs = res.json().get("preferences")
        except Exception:
            prefs = None

    if not prefs:
        st.info("Chưa có thông tin cá nhân hoá nào.")
    else:
        # map common preference keys to Vietnamese labels
        PREF_LABELS = {
            "salutation": "Xưng hô",
            "tone": "Giọng điệu",
            "language": "Ngôn ngữ",
            "favorite_subject": "Môn ưa thích",
            "display_name": "Tên hiển thị",
            "timezone": "Múi giờ",
        }
        # ensure prefs is a dict
        if isinstance(prefs, list):
            # some backends may return list of pairs; try to convert
            try:
                prefs = dict(prefs)
            except Exception:
                pass
        for k, v in (prefs.items() if isinstance(prefs, dict) else []):
            label = PREF_LABELS.get(k, k)
            c1, c2 = st.columns([6,1])
            with c1:
                st.write(f"**{label}**: {v}")
            with c2:
                if st.button("Xóa", key=f"pref_del_{k}"):
                    session = get_api_session()
                    try:
                        resp = session.delete(f"{API_URL}/user/preferences/{k}", timeout=5)
                    except requests.RequestException:
                        st.error("Lỗi khi gọi backend.")
                    else:
                        if resp.status_code == 200:
                            st.success("Đã xóa.")
                            # remove locally and refresh
                            try:
                                if isinstance(st.session_state.get("chat_sessions"), dict):
                                    pass
                            except Exception:
                                pass
                            st.rerun()
                        else:
                            detail = resp.json().get("detail") if resp.headers.get("Content-Type") == "application/json" else resp.text
                            st.error(f"Không thể xóa: {detail}")

    st.markdown("---")
    if st.button("Quay lại"):
        back = st.session_state.prev_route or "chat"
        set_route(back)

# =============== Sidebar Global Nav ===============
def render_global_nav():
    if not st.session_state.user:
        return
    with st.sidebar:
        st.markdown(
            """
            <style>
            div[data-testid="stSidebar"] {display: block !important;}
            header {visibility: visible !important;}
            #MainMenu {visibility: visible !important;}
            </style>
            """,
            unsafe_allow_html=True,
        )
        display_name = st.session_state.user.get("first_name") or ""
        if not display_name:
            profile_name = st.session_state.profile.get("name", "") if st.session_state.get("profile") else ""
            if profile_name:
                display_name = profile_name.strip().split(" ")[-1]
            else:
                full_name = st.session_state.user.get("name", "")
                if full_name:
                    display_name = full_name.strip().split(" ")[-1]
        if not display_name:
            display_name = st.session_state.user.get("username", "User")
        st.markdown(f"**👤 {display_name}**")
        st.markdown("---")
        # Cụm nút điều hướng dạng button
        # Chatbot
        if st.session_state.route == "chat":
            chat_clicked = st.button("💬 Chatbot", use_container_width=True, type="primary", key="nav_chat_active")
        else:
            chat_clicked = st.button("💬 Chatbot", use_container_width=True, key="nav_chat")
        # Data
        if st.session_state.route == "data":
            data_clicked = st.button("📊 Trực quan dữ liệu", use_container_width=True, type="primary", key="nav_data_active")
        else:
            data_clicked = st.button("📊 Trực quan dữ liệu", use_container_width=True, key="nav_data")
        # Settings
        if st.session_state.route == "settings":
            settings_clicked = st.button("⚙️ Cài đặt tài khoản", use_container_width=True, type="primary", key="nav_settings_active")
        else:
            settings_clicked = st.button("⚙️ Cài đặt tài khoản", use_container_width=True, key="nav_settings")
        developer_clicked = False
        if st.session_state.user.get("role") in {"developer", "admin"}:
            if st.session_state.route == "developer":
                developer_clicked = st.button("🛠️ Công cụ developer", use_container_width=True, type="primary", key="nav_developer_active")
            else:
                developer_clicked = st.button("🛠️ Công cụ developer", use_container_width=True, key="nav_developer")

        if chat_clicked and st.session_state.route != "chat":
            set_route("chat")
        if data_clicked and st.session_state.route != "data":
            set_route("data")
        if settings_clicked and st.session_state.route != "settings":
            set_route("settings", remember_prev=True)
        if developer_clicked and st.session_state.route != "developer":
            set_route("developer", remember_prev=True)


# =============== Study Update ===============
def render_study_update():
    st.title("Cập nhật thông tin học tập")
    data, error = fetch_study_scores()
    if error:
        st.error(f"Không thể tải dữ liệu: {error}")
        return

    scores = data.get("scores", [])
    actual_count = data.get("actual_count", 0)
    grade_display = data.get("grade_display", STUDY_GRADE_DISPLAY)
    semester_display = data.get("semester_display", STUDY_SEMESTER_DISPLAY)
    threshold_min = data.get("prediction_threshold_min", 5)
    threshold_max = data.get("prediction_threshold_max", 36)

    # Show warning messages based on actual_count
    if actual_count < threshold_min:
        st.warning(f"⚠️ Nhập điểm {threshold_min} môn trở lên để tiến hành dự đoán điểm các học kỳ tiếp theo.")
    elif actual_count < threshold_max:
        st.warning(
            "ℹ️ Thông tin điểm số thực tế ở hiện tại đang ít sẽ ảnh hưởng đến độ chính xác của các học kỳ quá xa. Bổ sung thông tin sẽ gia tăng độ chính xác."
        )

    # Grade selection for study update (editable here)
    grade_options = []
    grade_map = {}
    for g in STUDY_GRADE_ORDER:
        for s in STUDY_SEMESTER_ORDER[g]:
            display = f"{STUDY_SEMESTER_DISPLAY.get(s, s)} {STUDY_GRADE_DISPLAY.get(g, g)}"
            value = f"{s}_{g}"
            grade_options.append(display)
            grade_map[display] = value
    current_grade_val = st.session_state.profile.get("current_grade") if st.session_state.profile else None
    initial_display = None
    if current_grade_val:
        for disp, val in grade_map.items():
            if val == current_grade_val:
                initial_display = disp
                break
    selected_display = st.selectbox("Học kỳ hiện tại", options=grade_options, index=grade_options.index(initial_display) if initial_display in grade_options else 0)
    selected_grade = grade_map.get(selected_display)

    col_g1, col_g2 = st.columns([3,1])
    with col_g2:
        if st.button("Lưu", use_container_width=True, key="study_save_grade"):
            session = get_api_session()
            try:
                res = session.post(f"{API_URL}/auth/profile", json={"current_grade": selected_grade}, timeout=10)
                if res.status_code in (200, 204):
                    profile_data = res.json().get("profile", {}) if res.content else {}
                    for field, value in profile_data.items():
                        st.session_state.profile[field] = value or ""
                    st.success("Đã lưu Học kỳ")
                    # Refresh study scores/form values so UI reflects saved current_grade immediately
                    try:
                        fresh = session.get(f"{API_URL}/study/scores", timeout=10)
                        if fresh.status_code == 200:
                            data = fresh.json()
                            new_scores = data.get("scores", [])
                            st.session_state.study_form_values = {}
                            for itm in new_scores:
                                k = itm.get("key")
                                val = itm.get("actual") if itm.get("actual") is not None else itm.get("predicted")
                                if val is None:
                                    st.session_state.study_form_values[k] = ""
                                else:
                                    try:
                                        st.session_state.study_form_values[k] = f"{float(val):.1f}"
                                    except Exception:
                                        st.session_state.study_form_values[k] = str(val)
                            st.rerun()
                    except requests.RequestException:
                        pass
                else:
                    st.error(res.json().get("detail", "Không thể lưu Học kỳ."))
            except requests.RequestException as exc:
                st.error(f"Lỗi kết nối khi lưu Học kỳ: {exc}")

    grouped, _ = prepare_score_inputs(scores)
    # Build ordered slots and mapping for disabling inputs beyond current saved grade
    ordered_slots = []
    for g in STUDY_GRADE_ORDER:
        for s in STUDY_SEMESTER_ORDER[g]:
            ordered_slots.append((g, s))

    def slot_index_for_token(token: str) -> int | None:
        if not token:
            return None
        try:
            parts = str(token).split("_")
            if len(parts) != 2:
                return None
            sem, gr = parts[0].upper(), parts[1]
            for idx_slot, (g, s) in enumerate(ordered_slots):
                if g == gr and s == sem:
                    return idx_slot
        except Exception:
            return None
        return None

    active_idx = slot_index_for_token(current_grade_val)

    with st.form("study_scores_form"):
        for grade in STUDY_GRADE_ORDER:
            st.markdown(f"### {grade_display.get(grade, f'Lớp {grade}')}" )
            for semester in STUDY_SEMESTER_ORDER[grade]:
                st.markdown(f"**{semester_display.get(semester, 'Học kỳ')}**")
                subjects = grouped.get(grade, {}).get(semester, [])
                if not subjects:
                    st.info("Chưa có dữ liệu cho mục này.")
                    continue
                cols = st.columns(3)
                for idx, item in enumerate(subjects):
                    col = cols[idx % 3]
                    with col:
                        key = item["key"]
                        subject_label = get_subject_display_name(item["subject"])
                        actual = item.get("actual")
                        predicted = item.get("predicted")
                        status_text = "Thực tế" if actual is not None else ("Dự đoán" if predicted is not None else "Chưa có")
                        placeholder_value = DEFAULT_SCORE_PLACEHOLDER
                        if predicted is not None and actual is None:
                            try:
                                placeholder_value = f"{float(predicted):.1f}"
                            except (TypeError, ValueError):
                                placeholder_value = str(predicted)
                        input_col, status_col = st.columns([3, 1])
                        with input_col:
                            # disable inputs if this slot is after the user's active current grade
                            disable_input = False
                            try:
                                this_idx = None
                                for idx_slot, (g, s) in enumerate(ordered_slots):
                                    if g == grade and s == semester:
                                        this_idx = idx_slot
                                        break
                                if active_idx is not None and this_idx is not None and this_idx > active_idx:
                                    disable_input = True
                            except Exception:
                                disable_input = False
                            st.text_input(
                                subject_label,
                                key=key,
                                placeholder=placeholder_value,
                                disabled=disable_input,
                            )
                        status_class = {
                            "Thực tế": "actual",
                            "Dự đoán": "predicted",
                            "Chưa có": "empty",
                        }.get(status_text, "empty")
                        with status_col:
                            status_col.markdown(
                                f"<div class=\"score-status\"><span class=\"score-badge {status_class}\">{status_text}</span></div>",
                                unsafe_allow_html=True,
                            )
                            st.session_state.study_form_values[key] = st.session_state.get(key, "")
                st.markdown("---")
        submitted = st.form_submit_button("Lưu thông tin học tập", type="primary")

    if submitted:
        updates = []
        deletes = []
        for item in scores:
            key = item["key"]
            raw_value = st.session_state.get(key, "").strip()
            # determine index for this record so we can skip inputs beyond active_idx
            try:
                rec_idx = None
                for idx_slot, (g, s) in enumerate(ordered_slots):
                    if g == item["grade_level"] and s == item["semester"]:
                        rec_idx = idx_slot
                        break
            except Exception:
                rec_idx = None

            # If field is now empty but had a value before, mark for deletion
            if raw_value == "":
                if item.get("actual") is not None:
                    # Only delete if within allowed range (not after active_idx)
                    if not (active_idx is not None and rec_idx is not None and rec_idx > active_idx):
                        deletes.append({
                            "subject": item["subject"],
                            "grade_level": item["grade_level"],
                            "semester": item["semester"],
                        })
                continue
            
            try:
                normalized = round(float(raw_value.replace(",", ".")), 1)
            except ValueError:
                st.error(f"Điểm không hợp lệ cho {item['subject']} ({item['semester']}/{item['grade_level']}).")
                return
            # Skip saving scores for slots after active_idx
            if active_idx is not None and rec_idx is not None and rec_idx > active_idx:
                continue
            updates.append(
                {
                    "subject": item["subject"],
                    "grade_level": item["grade_level"],
                    "semester": item["semester"],
                    "score": normalized,
                }
            )
            formatted_val = f"{normalized:.1f}"
            st.session_state.study_form_values[key] = formatted_val
            st.session_state.pop(key, None)

        if not updates and not deletes:
            st.info("Không có thay đổi nào để cập nhật.")
            return

        session = get_api_session()
        
        # First, send deletions (if any)
        if deletes:
            try:
                res = session.post(f"{API_URL}/study/scores/delete", json={"scores": deletes}, timeout=15)
                if res.status_code != 200:
                    st.error(res.json().get("detail", "Không thể xóa một số mục."))
                    return
            except requests.RequestException as exc:
                st.error(f"Lỗi khi xóa: {exc}")
                return
        
        # Then, send updates (if any)
        if updates:
            try:
                res = session.post(f"{API_URL}/study/scores/bulk", json={"scores": updates}, timeout=15)
                if res.status_code != 200:
                    st.error(res.json().get("detail", "Không thể lưu dữ liệu."))
                    return
            except requests.RequestException as exc:
                st.error(f"Lỗi kết nối khi lưu dữ liệu: {exc}")
                return
        
        # Finally, refresh UI with latest data from server
        try:
            scores_res = session.get(f"{API_URL}/study/scores", timeout=15)
            scores_res.raise_for_status()
            scores_list = scores_res.json().get("scores", [])
            
            # Rebuild session state with fresh scores
            st.session_state.study_form_values = {}
            for score_item in scores_list:
                key = f"{score_item['subject']}_{score_item['grade_level']}_{score_item['semester']}"
                st.session_state.study_form_values[key] = f"{score_item.get('actual_score', '')} / {score_item.get('predicted_score', '')}"
            
            if deletes:
                st.success(f"✅ Đã xóa {len(deletes)} mục và cập nhật thông tin học tập!")
            else:
                st.success("✅ Cập nhật thông tin học tập thành công!")
            st.rerun()
        except Exception as e:
            st.warning(f"Cập nhật thành công nhưng không thể làm mới giao diện: {e}")
            st.rerun()


# =============== App ===============
init_state()
ensure_first_login_route()
current_route = st.session_state.route
if current_route == "auth":
    render_auth()
elif current_route == "first_time":
    render_first_time_profile()
else:
    render_global_nav()
    if current_route == "chat":
        render_chatbot()
    elif current_route == "data":
        render_data_viz()
    elif current_route == "settings":
        render_settings()
    elif current_route == "study":
        render_study_update()
    elif current_route == "sessions":
        render_sessions_manager()
    elif current_route == "developer":
        render_developer_tools()