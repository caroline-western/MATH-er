import math
import random
import sqlite3
import hashlib
import hmac
import os
from collections import Counter

import pandas as pd
import streamlit as st


# =========================================================
# MATH-ER AI - MATHEMATICS EDITION
# =========================================================

st.set_page_config(
    page_title="Math-er AI",
    layout="wide"
)


# -------------------- Accounts & persistent learning data --------------------

DB_PATH = os.environ.get("MATHER_DB_PATH", "mather_ai.db")


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS learning_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                score REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 310_000
    ).hex()
    return digest, salt


def create_account(username, password):
    username = username.strip()
    if len(username) < 3 or len(username) > 24:
        return False, "Username cần có từ 3 đến 24 ký tự."
    if not all(char.isalnum() or char in "._-" for char in username):
        return False, "Username chỉ được chứa chữ, số, dấu chấm, gạch ngang hoặc gạch dưới."
    if len(password) < 8:
        return False, "Password cần có ít nhất 8 ký tự."
    password_hash, salt = hash_password(password)
    try:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO users (username, password_hash, password_salt) VALUES (?, ?, ?)",
                (username, password_hash, salt)
            )
        return True, "Tạo tài khoản thành công. M đăng nhập nhé!"
    except sqlite3.IntegrityError:
        return False, "Username này đã tồn tại."


def authenticate(username, password):
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, username, password_hash, password_salt FROM users WHERE username = ?",
            (username.strip(),)
        ).fetchone()
    if user is None:
        return None
    candidate, _ = hash_password(password, user["password_salt"])
    if hmac.compare_digest(candidate, user["password_hash"]):
        return {"id": user["id"], "username": user["username"]}
    return None


def record_activity(user_id, activity_type, details="", score=None):
    with get_connection() as connection:
        connection.execute(
            """INSERT INTO learning_activity
               (user_id, activity_type, details, score)
               VALUES (?, ?, ?, ?)""",
            (user_id, activity_type, details, score)
        )


def get_user_activity(user_id):
    with get_connection() as connection:
        return pd.read_sql_query(
            """SELECT activity_type, details, score, created_at
               FROM learning_activity
               WHERE user_id = ?
               ORDER BY id DESC""",
            connection,
            params=(user_id,)
        )


initialize_database()

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("Math-er AI")
    st.caption("Đăng nhập để lưu và theo dõi tiến độ học tập của m.")

    login_tab, register_tab = st.tabs(["Đăng nhập", "Tạo tài khoản"])

    with login_tab:
        with st.form("login_form"):
            login_username = st.text_input("Username")
            login_password = st.text_input("Password", type="password")
            login_submitted = st.form_submit_button("Đăng nhập", type="primary")
        if login_submitted:
            user = authenticate(login_username, login_password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Username hoặc password chưa chính xác.")

    with register_tab:
        with st.form("register_form"):
            new_username = st.text_input("Tạo username")
            new_password = st.text_input("Tạo password", type="password")
            confirm_password = st.text_input("Nhập lại password", type="password")
            register_submitted = st.form_submit_button("Đăng ký", type="primary")
        if register_submitted:
            if new_password != confirm_password:
                st.error("Hai password không khớp.")
            else:
                success, message = create_account(new_username, new_password)
                (st.success if success else st.error)(message)
    st.stop()

CURRENT_USER = st.session_state.user


# -------------------- Calculation engines --------------------

def calculate_sequence(kind, first, step, n):
    """Calculate terms and sum of an arithmetic or geometric sequence."""
    if n < 1:
        raise ValueError("n phải là số nguyên dương.")

    if "cộng" in kind:
        terms = [first + i * step for i in range(n)]
        total = n * (2 * first + (n - 1) * step) / 2
        formula = (
            rf"u_n = u_1 + (n-1)d = {first:g} + (n-1)\cdot {step:g}"
        )
    else:
        terms = [first * (step ** i) for i in range(n)]
        if step == 1:
            total = n * first
        else:
            total = first * (step ** n - 1) / (step - 1)
        formula = (
            rf"u_n = u_1q^{{n-1}} = {first:g}\cdot {step:g}^{{n-1}}"
        )

    return {
        "terms": terms,
        "un": terms[-1],
        "sum": total,
        "formula": formula
    }


def quantile_linear(values, p):
    """Interpolate a quantile for raw data."""
    values = sorted(values)
    if not values:
        raise ValueError("Chưa có dữ liệu.")

    position = (len(values) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)

    return (
        values[lower]
        + (values[upper] - values[lower]) * (position - lower)
    )


def analyze_raw_data(values):
    """Create a frequency table and descriptive statistics from raw data."""
    if not values:
        raise ValueError("Hãy nhập ít nhất một giá trị.")

    if any(not math.isfinite(value) for value in values):
        raise ValueError("Dữ liệu phải là số hữu hạn.")

    counts = Counter(values)
    max_frequency = max(counts.values())

    modes = (
        sorted(
            value
            for value, frequency in counts.items()
            if frequency == max_frequency
        )
        if max_frequency > 1
        else []
    )

    unique_values = sorted(counts)

    table = pd.DataFrame({
        "Giá trị": unique_values,
        "Tần số": [counts[value] for value in unique_values]
    })

    sorted_values = sorted(values)

    return {
        "n": len(values),
        "table": table,
        "mean": sum(values) / len(values),
        "median": quantile_linear(sorted_values, 0.5),
        "q1": quantile_linear(sorted_values, 0.25),
        "q3": quantile_linear(sorted_values, 0.75),
        "modes": modes
    }


def analyze_grouped_data(rows):
    """Estimate statistics from grouped frequency data."""
    if not rows:
        raise ValueError("Hãy nhập ít nhất một lớp.")

    cleaned = []

    for lower, upper, frequency in rows:
        if upper <= lower:
            raise ValueError("Cận trên phải lớn hơn cận dưới.")

        if frequency < 0 or int(frequency) != frequency:
            raise ValueError("Tần số phải là số nguyên không âm.")

        cleaned.append((lower, upper, int(frequency)))

    cleaned.sort(key=lambda row: row[0])

    for index in range(1, len(cleaned)):
        if cleaned[index][0] < cleaned[index - 1][1]:
            raise ValueError("Các lớp không được chồng lấn.")

    n = sum(row[2] for row in cleaned)

    if n <= 0:
        raise ValueError("Tổng tần số phải lớn hơn 0.")

    midpoints = [
        (lower + upper) / 2
        for lower, upper, _ in cleaned
    ]

    mean = sum(
        midpoint * row[2]
        for midpoint, row in zip(midpoints, cleaned)
    ) / n

    cumulative_before = []
    running_total = 0

    for _, _, frequency in cleaned:
        cumulative_before.append(running_total)
        running_total += frequency

    def grouped_quantile(position):
        for (lower, upper, frequency), before in zip(
            cleaned, cumulative_before
        ):
            if frequency and position <= before + frequency:
                return lower + (
                    (position - before) / frequency
                ) * (upper - lower)

        return cleaned[-1][1]

    median = grouped_quantile(n / 2)
    q1 = grouped_quantile(n / 4)
    q3 = grouped_quantile(3 * n / 4)

    modal_index = max(
        range(len(cleaned)),
        key=lambda index: cleaned[index][2]
    )

    lower, upper, frequency = cleaned[modal_index]
    previous_frequency = (
        cleaned[modal_index - 1][2]
        if modal_index > 0
        else 0
    )
    next_frequency = (
        cleaned[modal_index + 1][2]
        if modal_index + 1 < len(cleaned)
        else 0
    )

    d1 = frequency - previous_frequency
    d2 = frequency - next_frequency

    mode = (
        lower + (d1 / (d1 + d2)) * (upper - lower)
        if d1 + d2
        else None
    )

    table = pd.DataFrame({
        "Lớp": [
            f"[{lower:g}; {upper:g})"
            for lower, upper, _ in cleaned
        ],
        "Điểm giữa": midpoints,
        "Tần số": [
            frequency
            for _, _, frequency in cleaned
        ],
        "Tần số tích lũy": [
            before + row[2]
            for before, row in zip(cumulative_before, cleaned)
        ]
    })

    return {
        "n": n,
        "table": table,
        "mean": mean,
        "median": median,
        "q1": q1,
        "q3": q3,
        "mode": mode
    }


def generate_sequence_questions(topic, difficulty, count):
    """Generate arithmetic and geometric sequence exercises."""
    output = []

    for _ in range(count):
        is_arithmetic = (
            topic == "Cấp số cộng"
            or (
                topic == "Trộn hai dạng"
                and random.choice([True, False])
            )
        )

        if is_arithmetic:
            first = random.randint(1, 10)
            difference = random.randint(2, 6)
            n = random.randint(4, 8)

            if difficulty == "Vận dụng":
                answer = (
                    n * (2 * first + (n - 1) * difference) // 2
                )
                question = (
                    f"Một CSC có u₁ = {first}, d = {difference}. "
                    f"Tính tổng {n} số hạng đầu."
                )
                explanation = (
                    f"S{n} = {n}/2 × [2×{first} + "
                    f"({n}−1)×{difference}] = {answer}."
                )
            else:
                answer = first + (n - 1) * difference
                question = (
                    f"Một CSC có u₁ = {first}, d = {difference}. "
                    f"Tính u{n}."
                )
                explanation = (
                    f"u{n} = {first} + ({n}−1)×"
                    f"{difference} = {answer}."
                )
        else:
            first = random.randint(1, 5)
            ratio = random.randint(2, 3)
            n = random.randint(3, 6)

            if difficulty == "Vận dụng":
                answer = first * (ratio ** n - 1) // (ratio - 1)
                question = (
                    f"Một CSN có u₁ = {first}, q = {ratio}. "
                    f"Tính tổng {n} số hạng đầu."
                )
                explanation = (
                    f"S{n} = {first}×({ratio}^{n}−1)/"
                    f"({ratio}−1) = {answer}."
                )
            else:
                answer = first * ratio ** (n - 1)
                question = (
                    f"Một CSN có u₁ = {first}, q = {ratio}. "
                    f"Tính u{n}."
                )
                explanation = (
                    f"u{n} = {first}×{ratio}^{n-1} = {answer}."
                )

        output.append({
            "question": question,
            "answer": answer,
            "explanation": explanation
        })

    return output


# -------------------- Page styling --------------------

st.markdown(
    """
    <style>
    .main {
        background-color: #f7f9fc;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .hero {
        padding: 1.5rem 1.7rem;
        border-radius: 18px;
        background: linear-gradient(120deg, #e9f2ff, #f3edff);
    }
    .hero h1 {
        margin: 0;
        color: #183153;
    }
    .hero p {
        margin: .45rem 0 0;
        color: #40536d;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# -------------------- Navigation --------------------

PAGES = [
    "Trang chủ",
    "Tiến độ học tập",
    "Sequence Calculator",
    "Statistics Lab",
    "Practice Generator",
    "Quiz Maker",
]

with st.sidebar:
    st.title("Welcome to :rainbow[Math-er AI]")
    st.caption("Your intelligent companion for mathematics")
    st.caption(f"Xin chào, **{CURRENT_USER['username']}**")
    if st.button("Đăng xuất"):
        st.session_state.user = None
        st.rerun()
    st.divider()
    page = st.radio(
    "Điều hướng",
    PAGES,
    key="page_navigation"
)
    st.caption("Mathematics Edition · Prototype 1.0")

st.title(page)

# =========================================================
# LEARNING PROGRESS
# =========================================================

if page == "Tiến độ học tập":
    st.subheader(f"Xin chào, {CURRENT_USER['username']}!")
    activity = get_user_activity(CURRENT_USER["id"])

    if activity.empty:
        st.info("Chưa có dữ liệu học tập. Bắt đầu sử dụng các công cụ để ghi lại tiến độ nhé!")
    else:
        total_activities = len(activity)
        quiz_activity = activity[activity["activity_type"] == "Quiz"]
        practice_count = int((activity["activity_type"] == "Practice").sum())
        average_score = quiz_activity["score"].dropna().mean() if not quiz_activity.empty else None

        metric1, metric2, metric3 = st.columns(3)
        metric1.metric("Tổng hoạt động", total_activities)
        metric2.metric("Lượt luyện tập", practice_count)
        metric3.metric("Điểm quiz trung bình",
                       f"{average_score:.1f}/10" if pd.notna(average_score) else "Chưa có")

        st.subheader("Lịch sử học tập")
        history = activity.rename(columns={
            "activity_type": "Hoạt động",
            "details": "Chi tiết",
            "score": "Điểm (/10)",
            "created_at": "Thời gian"
        })
        st.dataframe(history, use_container_width=True, hide_index=True)

        st.subheader("Thống kê hoạt động")
        counts = activity["activity_type"].value_counts()
        st.bar_chart(counts)

# =========================================================
# HOME PAGE
# =========================================================

elif page == "Trang chủ":
    st.markdown(
        '<div class="hero">'
        '<h1>Learn smarter, step by step.</h1>'
        '<p>Không gian học Toán 11 với công cụ tính toán, '
        'luyện tập và kiểm tra kiến thức.</p>'
        '</div>',
        unsafe_allow_html=True
    )

    st.write("")

    c1, c2, c3 = st.columns(3)
    c1.metric("Công cụ tính toán", "2", "Dãy số & thống kê")
    c2.metric("Công cụ luyện tập", "2", "Practice & Quiz")
    c3.metric("Chi phí bản nền tảng", "0đ")

    st.subheader("Việc gì khó, có Math-er lo!")

    left, right = st.columns(2)

    left.info(
        "**Sequence Calculator**\n\n"
        "Tính số hạng, tổng và liệt kê các số hạng của CSC/CSN."
    )
    left.info(
        "**Statistics Lab**\n\n"
        "Nhập dữ liệu không ghép nhóm hoặc bảng dữ liệu ghép nhóm."
    )
    right.info(
        "**Practice Generator**\n\n"
        "Tạo bài tập luyện tập về CSC và CSN."
    )
    right.info(
        "**Quiz Maker**\n\n"
        "Làm bài kiểm tra ngắn, chấm điểm và xem giải thích."
    )

# =========================================================
# SEQUENCE CALCULATOR
# =========================================================

elif page == "Sequence Calculator":
    st.write(
        "Tính số hạng và tổng của cấp số cộng hoặc cấp số nhân."
    )

    kind = st.radio(
        "Loại dãy",
        ["Cấp số cộng (CSC)", "Cấp số nhân (CSN)"],
        horizontal=True
    )

    col1, col2 = st.columns(2)

    first_term = col1.number_input(
        "Số hạng đầu u₁",
        value=2.0
    )
    step = col2.number_input(
        "Công sai d / Công bội q",
        value=3.0
    )

    n = st.number_input(
        "Số số hạng n",
        min_value=1,
        max_value=100000,
        value=10,
        step=1
    )

    if st.button("Tính toán", type="primary"):
        result = calculate_sequence(
            kind,
            float(first_term),
            float(step),
            int(n)
        )
        record_activity(
            CURRENT_USER["id"], "Sequence Calculator",
            f"{kind}; u1={first_term}; công sai/bội={step}; n={n}"
        )

        a, b, c = st.columns(3)
        a.metric(f"u{n}", f"{result['un']:.8g}")
        b.metric(f"S{n}", f"{result['sum']:.8g}")
        c.metric("Số số hạng", int(n))

        st.dataframe(
            {
                "n": range(1, int(n) + 1),
                "uₙ": result["terms"]
            },
            use_container_width=True,
            hide_index=True
        )

        st.latex(result["formula"])


# =========================================================
# STATISTICS LAB
# =========================================================

elif page == "Statistics Lab":
    mode = st.radio(
        "Cách nhập dữ liệu",
        ["Dữ liệu không ghép nhóm", "Bảng tần số ghép nhóm"],
        horizontal=True
    )

    if mode == "Dữ liệu không ghép nhóm":
        raw = st.text_area(
            "Nhập số, phân cách bằng dấu phẩy, dấu cách hoặc xuống dòng",
            "5, 6, 7, 7, 8, 8, 8, 9, 10"
        )

        if st.button("Phân tích dữ liệu", type="primary"):
            try:
                values = [
                    float(value)
                    for value in raw.replace(",", " ").replace(";", " ").split()
                ]

                result = analyze_raw_data(values)
                record_activity(
                    CURRENT_USER["id"], "Statistics Lab",
                    f"Phân tích dữ liệu không ghép nhóm ({len(values)} giá trị)"
                )

                st.metric("Số quan sát", result["n"])
                st.dataframe(
                    result["table"],
                    use_container_width=True,
                    hide_index=True
                )

                cols = st.columns(4)

                for col, label, key in zip(
                    cols,
                    ["Trung bình", "Trung vị", "Q1", "Q3"],
                    ["mean", "median", "q1", "q3"]
                ):
                    col.metric(label, f"{result[key]:.4g}")

                mode_text = (
                    ", ".join(map(str, result["modes"]))
                    if result["modes"]
                    else "Không có"
                )
                st.metric("Mốt", mode_text)

                st.bar_chart(
                    result["table"].set_index("Giá trị")["Tần số"]
                )

            except Exception as error:
                st.error(f"Dữ liệu chưa hợp lệ: {error}")

    else:
        st.write(
            "Mỗi dòng theo định dạng: **cận dưới, cận trên, tần số**."
        )

        raw_grouped = st.text_area(
            "Bảng tần số",
            "0, 10, 3\n10, 20, 7\n20, 30, 5\n30, 40, 2"
        )

        if st.button(
            "Phân tích bảng ghép nhóm",
            type="primary"
        ):
            try:
                rows = []

                for line in raw_grouped.strip().splitlines():
                    parts = [
                        float(value.strip())
                        for value in line.split(",")
                    ]

                    if len(parts) != 3:
                        raise ValueError(
                            "Mỗi dòng cần đúng 3 số."
                        )

                    rows.append(parts)

                result = analyze_grouped_data(rows)
                record_activity(
                    CURRENT_USER["id"], "Statistics Lab",
                    f"Phân tích bảng ghép nhóm ({len(rows)} lớp)"
                )

                st.metric("Tổng tần số n", result["n"])
                st.dataframe(
                    result["table"],
                    use_container_width=True,
                    hide_index=True
                )

                cols = st.columns(4)

                for col, label, key in zip(
                    cols,
                    [
                        "Trung bình (ước lượng)",
                        "Trung vị (ước lượng)",
                        "Q1 (ước lượng)",
                        "Q3 (ước lượng)"
                    ],
                    ["mean", "median", "q1", "q3"]
                ):
                    col.metric(label, f"{result[key]:.4g}")

                st.metric(
                    "Mốt (ước lượng)",
                    f"{result['mode']:.4g}"
                    if result["mode"] is not None
                    else "Chưa xác định"
                )

                st.bar_chart(
                    result["table"].set_index("Lớp")["Tần số"]
                )

                st.warning(
                    "Các kết quả của dữ liệu ghép nhóm là giá trị "
                    "ước lượng từ lớp và tần số."
                )

            except Exception as error:
                st.error(f"Bảng chưa hợp lệ: {error}")


# =========================================================
# PRACTICE GENERATOR
# =========================================================

elif page == "Practice Generator":
    topic = st.selectbox(
        "Chủ đề",
        ["Cấp số cộng", "Cấp số nhân", "Trộn hai dạng"]
    )

    difficulty = st.selectbox(
        "Mức độ",
        ["Cơ bản", "Vận dụng"]
    )
    question_count = st.slider("Số câu hỏi", 1, 10, 5)

    if st.button("Tạo bài tập", type="primary"):
        st.session_state.practice_questions = generate_sequence_questions(
            topic, difficulty, question_count
        )
        st.session_state.practice_completed = False
        record_activity(
            CURRENT_USER["id"], "Practice",
            f"Tạo {question_count} câu · {topic} · {difficulty}"
        )

    practice_questions = st.session_state.get("practice_questions", [])
    for index, question in enumerate(practice_questions, 1):
        with st.expander(f"Câu {index}: {question['question']}"):
            st.write(f"**Đáp án:** {question['answer']}")
            st.write(question["explanation"])

    if practice_questions:
        completed = st.checkbox(
            "T đánh dấu đã hoàn thành bài luyện tập này",
            value=st.session_state.get("practice_completed", False)
        )
        if completed and not st.session_state.get("practice_completed", False):
            record_activity(
                CURRENT_USER["id"], "Practice completed",
                f"Hoàn thành {len(practice_questions)} câu luyện tập"
            )
        st.session_state.practice_completed = completed


# =========================================================
# QUIZ MAKER
# =========================================================

elif page == "Quiz Maker":
    questions = [
        {
            "q": "Một CSC có u₁ = 4, d = 3. u₅ bằng bao nhiêu?",
            "opts": ["13", "16", "19", "20"],
            "a": "16",
            "why": "u₅ = 4 + 4×3 = 16."
        },
        {
            "q": "Một CSN có u₁ = 2, q = 3. u₄ bằng bao nhiêu?",
            "opts": ["18", "27", "54", "81"],
            "a": "54",
            "why": "u₄ = 2×3³ = 54."
        },
        {
            "q": "Tổng 5 số hạng đầu của CSC u₁ = 1, d = 2 là:",
            "opts": ["15", "20", "25", "30"],
            "a": "25",
            "why": "S₅ = 5/2 × (2×1 + 4×2) = 25."
        },
        {
            "q": "CSN có u₁ = 5, q = 1. S₄ bằng:",
            "opts": ["5", "10", "15", "20"],
            "a": "20",
            "why": "Bốn số hạng đều bằng 5 nên S₄ = 20."
        },
        {
            "q": "Công thức số hạng tổng quát của CSC là:",
            "opts": [
                "uₙ=u₁qⁿ⁻¹",
                "uₙ=u₁+(n−1)d",
                "uₙ=u₁+nd",
                "uₙ=u₁dⁿ"
            ],
            "a": "uₙ=u₁+(n−1)d",
            "why": "Đây là công thức số hạng tổng quát của CSC."
        }
    ]

    with st.form("quiz_form"):
        answers = {}

        for index, question in enumerate(questions):
            st.markdown(
                f"**Câu {index + 1}. {question['q']}**"
            )

            answers[index] = st.radio(
                "Chọn đáp án",
                question["opts"],
                key=f"quiz_{index}",
                index=None,
                label_visibility="collapsed"
            )

        submitted = st.form_submit_button(
            "Nộp bài",
            type="primary"
        )

    if submitted:
        score = sum(
            answers[index] == question["a"]
            for index, question in enumerate(questions)
        )
        score_out_of_10 = score / len(questions) * 10
        record_activity(
            CURRENT_USER["id"], "Quiz",
            f"{score}/{len(questions)} câu đúng",
            score_out_of_10
        )

        st.success(
            f"Kết quả: {score}/{len(questions)} câu đúng "
            f"({score / len(questions) * 10:.1f}/10 điểm)."
        )

        for index, question in enumerate(questions):
            is_correct = answers[index] == question["a"]

            st.write(
                f"**Câu {index + 1}:** "
                f"{'Đúng' if is_correct else 'Chưa đúng'} "
                f"· Đáp án: {question['a']}"
            )
            st.caption(question["why"])

# -------------------- Footer --------------------

st.divider()
st.caption("Math-er AI · Mathematics Edition · Prototype 1.0")

