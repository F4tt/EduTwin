import streamlit as st
import requests
import os
from datetime import datetime
from typing import Dict, List, Any

API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


STUDY_SUBJECTS = [
    "Toán",
    "Ngữ văn",
    "Vật lý",
    "Hóa học",
    "Sinh học",
    "Lịch sử",
    "Địa lý",
    "Tiếng Anh",
    "Giáo dục công dân",
]

STUDY_GRADE_ORDER = ["10", "11", "12", "TN"]
STUDY_SEMESTER_ORDER: Dict[str, List[str]] = {
    "10": ["1", "2"],
    "11": ["1", "2"],
    "12": ["1", "2"],
    "TN": ["TN"],
}
STUDY_GRADE_DISPLAY = {
    "10": "Lớp 10",
    "11": "Lớp 11",
    "12": "Lớp 12",
    "TN": "Tốt nghiệp",
}
STUDY_SEMESTER_DISPLAY = {"1": "Học kỳ 1", "2": "Học kỳ 2", "TN": "Kỳ thi tốt nghiệp"}
DEFAULT_SCORE_PLACEHOLDER = "VD: 8.5"


def get_api_session() -> requests.Session:
    if "api_session" not in st.session_state:
        st.session_state.api_session = requests.Session()
    return st.session_state.api_session


def is_valid_username(username: str) -> bool:
    return bool(username) and username.isascii() and all(ch.isalnum() or ch in {"_", "-"} for ch in username)


def is_ascii_text(value: str) -> bool:
    return bool(value) and value.isascii()

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
        st.session_state.route = "auth"  # auth | first_time | chat | data | settings
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
                                })
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
def render_first_time_profile():
    st.markdown(
        """
        <style>
        div[data-testid="stSidebar"] {display: none !important;}
        header {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        .first-time-wrapper {padding: 24px 6vw 80px; min-height: 100vh; background: #fafafa; display:flex; justify-content:center; align-items:flex-start;}
        .first-time-card {width: 100%; max-width: 860px; margin-top: 24px; background: #ffffff; padding: 40px 48px; border-radius: 18px; box-shadow: 0 16px 45px rgba(0,0,0,0.08);}
        </style>
        """,
        unsafe_allow_html=True,
    )

    step = st.session_state.get("first_time_step", "profile")
    st.session_state.first_time_step = step

    st.markdown("<div class='first-time-wrapper'><div class='first-time-card'>", unsafe_allow_html=True)

    if step == "profile":
        st.markdown("### Chào mừng bạn đến với EduTwin 👋")
        st.write("Hãy bổ sung một vài thông tin liên hệ để cá nhân hoá trải nghiệm (không bắt buộc).")
        with st.form("first_time_profile_form"):
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Email", value=st.session_state.profile.get("email", ""), placeholder="VD: ten@example.com")
                address = st.text_input("Địa chỉ", value=st.session_state.profile.get("address", ""), placeholder="VD: 123 Nguyễn Huệ, Quận 1")
            with col2:
                phone = st.text_input("Số điện thoại", value=st.session_state.profile.get("phone", ""), placeholder="VD: 0912 345 678")
                age = st.text_input("Tuổi", value=st.session_state.profile.get("age", ""), placeholder="VD: 16")
            continue_clicked = st.form_submit_button("Tiếp tục", type="primary", use_container_width=True)
        if continue_clicked:
            st.session_state.profile.update({
                "email": email.strip(),
                "phone": phone.strip(),
                "address": address.strip(),
                "age": age.strip(),
            })
            payload = {
                "email": email.strip() or None,
                "phone": phone.strip() or None,
                "address": address.strip() or None,
                "age": age.strip() or None,
            }
            session = get_api_session()
            try:
                res = session.post(f"{API_URL}/auth/profile", json=payload, timeout=10)
                if res.status_code in (200, 204):
                    profile_data = res.json().get("profile", {}) if res.content else {}
                    for field, value in profile_data.items():
                        st.session_state.profile[field] = value or ""
                    st.session_state.first_time_step = "scores"
                    st.rerun()
                else:
                    detail = res.json().get("detail", "Không thể lưu thông tin.")
                    st.error(detail)
            except requests.RequestException as exc:
                st.error(f"Lỗi kết nối khi lưu thông tin: {exc}")

    elif step == "scores":
        st.markdown("### Nhập điểm các môn học")
        st.write("Bạn có thể điền những điểm đã có. Nếu chưa sẵn sàng, hãy bấm \"Bỏ qua\" để hoàn tất sau.")
        data, error = fetch_study_scores()
        if error:
            st.error(f"Không thể tải dữ liệu: {error}")
        else:
            scores = data.get("scores", [])
            grade_display = data.get("grade_display", STUDY_GRADE_DISPLAY)
            semester_display = data.get("semester_display", STUDY_SEMESTER_DISPLAY)
            grouped, score_keys = prepare_score_inputs(scores)
            has_input = any(str(st.session_state.get(key, "")).strip() for key in score_keys)

            with st.form("first_time_scores_form"):
                for grade in STUDY_GRADE_ORDER:
                    st.markdown(f"#### {grade_display.get(grade, f'Lớp {grade}')}")
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
                                subject_label = item["subject"]
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
                                    st.text_input(
                                        subject_label,
                                        key=key,
                                        placeholder=placeholder_value,
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
                        st.markdown("---")
                save_clicked = st.form_submit_button(
                    "Lưu", type="primary", use_container_width=True, disabled=not has_input
                )

            if save_clicked:
                updates = []
                for item in scores:
                    key = item["key"]
                    raw_value = str(st.session_state.get(key, "")).strip()
                    if not raw_value:
                        continue
                    try:
                        normalized = round(float(raw_value.replace(",", ".")), 1)
                    except ValueError:
                        st.error(f"Điểm không hợp lệ cho {item['subject']} ({item['semester']}/{item['grade_level']}).")
                        st.stop()
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

                if updates:
                    session = get_api_session()
                    try:
                        res = session.post(f"{API_URL}/study/scores/bulk", json={"scores": updates}, timeout=15)
                        if res.status_code == 200:
                            st.success("Đã cập nhật điểm học tập.")
                            for item in scores:
                                st.session_state.pop(item["key"], None)
                            st.session_state.pop("study_form_values", None)
                            st.session_state.first_time_step = None
                            st.session_state.is_first_login = False
                            set_route("chat")
                        else:
                            st.error(res.json().get("detail", "Không thể lưu dữ liệu."))
                    except requests.RequestException as exc:
                        st.error(f"Lỗi kết nối khi lưu dữ liệu: {exc}")

        st.markdown("""<div style='height:12px'></div>""", unsafe_allow_html=True)
        col_back, col_skip = st.columns([1, 1])
        with col_back:
            if st.button("Trở lại", key="first_time_back", use_container_width=True):
                st.session_state.first_time_step = "profile"
                st.rerun()
        with col_skip:
            if st.button("Bỏ qua", key="first_time_skip", use_container_width=True):
                st.session_state.first_time_step = None
                st.session_state.is_first_login = False
                st.session_state.pop("study_form_values", None)
                set_route("chat")

    st.markdown("</div></div>", unsafe_allow_html=True)


# =============== Các hàm khác (chat, data, settings, study) giữ nguyên ===============
# --- (các phần này bạn không cần chỉnh vì không có lỗi cú pháp) ---

# =============== Chatbot with Sessions ===============
def ensure_chat_session():
    if not st.session_state.current_session_id:
        sid = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        st.session_state.chat_sessions[sid] = {"title": f"Phiên {sid[-4:]}", "messages": []}
        st.session_state.current_session_id = sid


def render_chatbot():
    ensure_chat_session()
    with st.sidebar:
        st.header("💬 Phiên trò chuyện")
        if st.button("➕ Tạo phiên mới", use_container_width=True):
            sid = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            st.session_state.chat_sessions[sid] = {"title": f"Phiên {sid[-4:]}", "messages": []}
            st.session_state.current_session_id = sid
            st.rerun()
        if st.button("🗂️ Quản lý phiên", use_container_width=True):
            set_route("sessions", remember_prev=True)
        
        for sid, sess in list(sorted(st.session_state.chat_sessions.items())):
            if st.button(sess["title"], key=f"sess_{sid}", use_container_width=True):
                st.session_state.current_session_id = sid
                st.rerun()

        st.markdown("---")
        if st.button("📚 Cập nhật thông tin học tập", use_container_width=True):
            set_route("study", remember_prev=True)

    st.title("Chatbot (kết nối LLM – sẽ bổ sung)")
    current = st.session_state.chat_sessions[st.session_state.current_session_id]
    msgs = current["messages"]

    # Hiển thị lịch sử
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        with st.chat_message("assistant" if role == "assistant" else "user"):
            st.write(content)

    # Ô nhập
    prompt = st.chat_input("Nhập tin nhắn...")
    if prompt:
        msgs.append({"role": "user", "content": prompt})
        # Placeholder gọi LLM nội bộ (sẽ tích hợp sau). Tạm thời phản hồi giả lập.
        try:
            # resp = requests.post(f"{API_URL}/llm/chat", json={"session_id": st.session_state.current_session_id, "message": prompt})
            # ans = resp.json().get("answer", "...") if resp.status_code == 200 else "LLM chưa cấu hình."
            ans = "(Phản hồi mẫu) LLM sẽ được tích hợp sau."
        except Exception:
            ans = "Không thể kết nối LLM."
        msgs.append({"role": "assistant", "content": ans})
        st.rerun()

    # (Đã xoá modal quản lý phiên theo yêu cầu)
        

# =============== Data Visualization ===============
def render_data_viz():
    st.title("Trực quan dữ liệu người dùng")
    with st.sidebar:
        st.markdown("---")
        if st.button("📚 Cập nhật thông tin học tập", use_container_width=True):
            set_route("study", remember_prev=True)
    data, error = fetch_study_scores()
    if error:
        st.error(f"Không thể tải dữ liệu: {error}")
        return

    scores = data.get("scores", [])
    rows = []
    for item in scores:
        actual = item.get("actual")
        predicted = item.get("predicted")
        grade_label = STUDY_GRADE_DISPLAY.get(item["grade_level"], item["grade_level"])
        semester_label = STUDY_SEMESTER_DISPLAY.get(item["semester"], item["semester"])
        if actual is not None:
            rows.append(
                {
                    "Môn": item["subject"],
                    "Lớp": grade_label,
                    "Kỳ": semester_label,
                    "Điểm": actual,
                    "Nguồn": "Thực tế",
                }
            )
        elif predicted is not None:
            rows.append(
                {
                    "Môn": item["subject"],
                    "Lớp": grade_label,
                    "Kỳ": semester_label,
                    "Điểm": predicted,
                    "Nguồn": "Dự đoán",
                }
            )

    if not rows:
        st.info("Chưa có điểm số để trực quan hóa. Hãy cập nhật thông tin học tập trước.")
        return

    import pandas as pd

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    df_for_chart = df[df["Nguồn"] == "Thực tế"].copy()
    if df_for_chart.empty:
        df_for_chart = df.copy()

    chart_df = (
        df_for_chart.pivot_table(index="Môn", values="Điểm", aggfunc="mean")
        .sort_values("Điểm", ascending=False)
    )
    st.bar_chart(chart_df)


# =============== Settings ===============
def render_settings():
    st.title("Cài đặt tài khoản")
    name = st.text_input("Họ và tên", value=st.session_state.profile.get("name", ""))
    email = st.text_input("Email", value=st.session_state.profile.get("email", ""))
    phone = st.text_input("Số điện thoại", value=st.session_state.profile.get("phone", ""))
    address = st.text_input("Địa chỉ", value=st.session_state.profile.get("address", ""))
    age = st.text_input("Tuổi", value=st.session_state.profile.get("age", ""))
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
            for k in ["user", "profile", "is_first_login", "chat_sessions", "current_session_id"]:
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
    st.caption("Xem và xoá các phiên đã tồn tại.")
    if not st.session_state.chat_sessions:
        st.info("Chưa có phiên nào. Hãy tạo phiên mới trong Chatbot.")
    else:
        for sid, sess in list(sorted(st.session_state.chat_sessions.items())):
            c1, c2 = st.columns([4,1])
            with c1:
                st.write(sess.get("title", sid))
            with c2:
                if st.button("🗑️ Xoá", key=f"sessions_del_{sid}"):
                    st.session_state["session_to_delete"] = sid
                    st.session_state["confirm_delete"] = True
        if st.session_state.get("confirm_delete"):
            st.markdown("---")
            st.warning("Xác nhận xoá phiên đã chọn?")
            cc1, cc2 = st.columns([1,1])
            with cc1:
                if st.button("Hủy", key="sessions_cancel"):
                    st.session_state["confirm_delete"] = False
                    st.session_state["session_to_delete"] = None
                    st.rerun()
            with cc2:
                if st.button("Xóa", key="sessions_confirm"):
                    sid = st.session_state.get("session_to_delete")
                    if sid and sid in st.session_state.chat_sessions:
                        deleting_current = sid == st.session_state.current_session_id
                        del st.session_state.chat_sessions[sid]
                        if deleting_current:
                            if st.session_state.chat_sessions:
                                st.session_state.current_session_id = next(iter(st.session_state.chat_sessions.keys()))
                            else:
                                st.session_state.current_session_id = None
                                ensure_chat_session()
                    st.session_state["confirm_delete"] = False
                    st.session_state["session_to_delete"] = None
                    st.rerun()
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

        if chat_clicked and st.session_state.route != "chat":
            set_route("chat")
        if data_clicked and st.session_state.route != "data":
            set_route("data")
        if settings_clicked and st.session_state.route != "settings":
            set_route("settings", remember_prev=True)


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

    if actual_count < 18:
        st.warning(
            "Thông tin điểm số hiện tại đang quá ít sẽ ảnh hưởng đến độ chính xác của dự đoán. Bổ sung thông tin sẽ gia tăng độ chính xác."
        )

    grouped, _ = prepare_score_inputs(scores)

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
                        subject_label = item["subject"]
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
                            st.text_input(
                                subject_label,
                                key=key,
                                placeholder=placeholder_value,
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
        for item in scores:
            key = item["key"]
            raw_value = st.session_state.get(key, "").strip()
            if raw_value == "":
                continue
            try:
                normalized = round(float(raw_value.replace(",", ".")), 1)
            except ValueError:
                st.error(f"Điểm không hợp lệ cho {item['subject']} ({item['semester']}/{item['grade_level']}).")
                return
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
        if not updates:
            st.info("Không có điểm nào được cập nhật.")
            return

        session = get_api_session()
        try:
            res = session.post(f"{API_URL}/study/scores/bulk", json={"scores": updates}, timeout=15)
            if res.status_code == 200:
                st.success("Đã cập nhật điểm học tập.")
                for item in scores:
                    st.session_state.pop(item["key"], None)
                st.session_state.pop("study_form_values", None)
                st.rerun()
            else:
                st.error(res.json().get("detail", "Không thể lưu dữ liệu."))
        except requests.RequestException as exc:
            st.error(f"Lỗi kết nối khi lưu dữ liệu: {exc}")


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
