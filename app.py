import os
import hashlib
import threading
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from services.data_service import email_column, read_dataset, validate
from services.database_service import connect, history
from services.email_service import MAX_ATTACHMENT, SMTPConfig, send_batch
from services.template_service import render_template

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
DB_PATH = os.getenv("DATABASE_PATH", str(ROOT / "data" / "email_automation.sqlite3"))
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
connect(DB_PATH).close()

st.set_page_config(page_title="Email Automation", page_icon="✉️", layout="wide")
st.markdown("""<style>
  .block-container {max-width: 1120px; padding-top: 1.5rem}
  h1 {font-size: 1.6rem !important; letter-spacing: -.03em}
  [data-testid="stMetric"] {border: 1px solid #e3e8ef; border-radius: 10px; padding: 12px 16px; background: #fff}
  [data-testid="stFileUploader"] {border: 1px dashed #97abd0; border-radius: 10px; padding: 8px}
  .stButton button[kind="primary"] {background: #275cdd}
  .hint {color: #64748b; font-size: .85rem}
</style>""", unsafe_allow_html=True)


def smtp_config():
    return SMTPConfig(
        os.getenv("SMTP_HOST", "smtp.gmail.com"),
        int(os.getenv("SMTP_PORT", "587")),
        os.getenv("SMTP_USERNAME", ""),
        os.getenv("SMTP_PASSWORD", ""),
        os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USERNAME", "")),
        os.getenv("SMTP_SECURITY", "starttls").lower(),
    )


def reset():
    for key in ("uploaded", "mode", "test_email", "subject", "body", "campaign", "job", "retry_only", "dataset_fingerprint", "live_confirmed"):
        st.session_state.pop(key, None)
    st.rerun()


def run_job(job, kwargs):
    try:
        def progress(items):
            with job["lock"]:
                job["results"] = list(items)
        send_batch(**kwargs, on_progress=progress)
    except Exception as exc:
        with job["lock"]:
            job["error"] = str(exc)
    finally:
        with job["lock"]:
            job["done"] = True


def launch(kwargs):
    job = {"lock": threading.Lock(), "results": [], "error": "", "done": False}
    st.session_state.job = job
    threading.Thread(target=run_job, args=(job, kwargs), daemon=True).start()
    st.rerun()


@st.fragment(run_every="1s")
def results_panel(campaign, mode, expected):
    job = st.session_state.get("job")
    rows = history(DB_PATH, campaign, mode)
    sent = sum(row[4] == "Sent" for row in rows)
    failed = sum(row[4] in {"Failed", "Unknown"} for row in rows)
    skipped = 0
    processed = len(rows)
    done = True
    error = ""
    if job:
        with job["lock"]:
            snapshot = list(job["results"])
            done = job["done"]
            error = job["error"]
        processed = len(snapshot)
        skipped = sum(item[1] == "Skipped" for item in snapshot)
    st.progress(min(processed / max(expected, 1), 1.0))
    st.caption(f"Đã xử lý {processed}/{expected} · SMTP chấp nhận {sent} · Thất bại/chưa rõ {failed} · Bỏ qua {skipped}")
    if error:
        st.error(error)
    elif job and done:
        st.success("Đợt gửi đã hoàn tất. Trạng thái Sent nghĩa là SMTP đã chấp nhận.")
    if rows:
        result = pd.DataFrame(rows, columns=["Email", "Tiêu đề", "Thời gian", "Chế độ", "Trạng thái", "Lỗi"])
        st.dataframe(result, hide_index=True, use_container_width=True, height=230)
        st.download_button("Tải log CSV", result.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"send-log-{campaign}.csv", mime="text/csv")


config = smtp_config()
if "mode" not in st.session_state:
    st.session_state.mode = "Test"

head, status = st.columns([3, 1])
with head:
    st.title("✉️ Email Automation")
with status:
    st.caption("SMTP đã cấu hình" if config.ready else "SMTP chưa cấu hình")
st.radio("Chế độ gửi", ["Test", "Live"], horizontal=True, key="mode",
         format_func=lambda value: "Test Mode" if value == "Test" else "Live Mode")
if st.session_state.mode == "Live":
    live_confirmed = st.checkbox("Tôi xác nhận chuyển sang Live Mode", key="live_confirmed")
else:
    st.session_state.live_confirmed = False
    live_confirmed = False
st.divider()

uploaded = st.file_uploader("Kéo thả file Excel / CSV", type=["xlsx", "csv"], key="uploaded")
if uploaded is None:
    st.info("Tải lên danh sách để bắt đầu. Có thể thử với data/sample_dataset.csv.")
    if st.button("Reset"):
        reset()
    st.stop()
try:
    frame = read_dataset(uploaded.name, uploaded.getvalue())
    validated = validate(frame)
    email_col = email_column(frame)
except Exception as exc:
    st.error(f"Không đọc được dữ liệu: {exc}")
    st.stop()
fingerprint = hashlib.sha256(uploaded.getvalue()).hexdigest()[:12]
if st.session_state.get("dataset_fingerprint") != fingerprint:
    st.session_state.dataset_fingerprint = fingerprint
    st.session_state.campaign = fingerprint

st.caption(f"📄 {uploaded.name} · {len(frame)} bản ghi · Cột email: {email_col}")
total = len(validated)
valid_count = sum(validated["Trạng thái dữ liệu"] == "Hợp lệ")
previous = history(DB_PATH, st.session_state.campaign, st.session_state.mode)
metrics = st.columns(5)
for cell, label, value in zip(metrics,
    ["Tổng dữ liệu", "Hợp lệ", "Không hợp lệ", "Đã gửi", "Thất bại"],
    [total, valid_count, total - valid_count, sum(r[4] == "Sent" for r in previous),
     sum(r[4] in {"Failed", "Unknown"} for r in previous)]):
    cell.metric(label, value)

st.subheader("Danh sách người nhận")
search = st.text_input("Tìm kiếm", placeholder="Tên, email hoặc giá trị khác…")
filtered = validated
if search:
    matched = validated.astype(str).apply(lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
    filtered = filtered[matched]
filter_cols = [c for c in frame.columns if c != email_col and frame[c].nunique() <= 30]
if filter_cols:
    field = st.selectbox("Lọc theo cột", ["Không lọc"] + filter_cols)
    if field != "Không lọc":
        values = st.multiselect("Giá trị", sorted(frame[field].dropna().unique().tolist()))
        if values:
            filtered = filtered[filtered[field].isin(values)]
edited = st.data_editor(filtered, hide_index=True, use_container_width=True, height=230,
    disabled=[c for c in filtered.columns if c != "Chọn"],
    column_config={"Chọn": st.column_config.CheckboxColumn("Chọn", help="Chỉ bản ghi hợp lệ được gửi")})
selected_indices = [idx for idx, row in edited.iterrows()
                    if bool(row["Chọn"]) and row["Trạng thái dữ liệu"] == "Hợp lệ"]
selected = frame.loc[selected_indices].to_dict("records")
st.caption(f"Người nhận thực tế: {len(selected)}")

st.divider()
st.subheader("Soạn email")
subject = st.text_input("Tiêu đề", value="Thông báo kết quả học tập", key="subject")
body = st.text_area("Nội dung", value="Xin chào {{ name }},\n\nKết quả học tập của bạn là {{ score }}.\n\nTrân trọng,", height=150, key="body")
st.caption("Biến có thể dùng: " + " · ".join("{{ " + str(c) + " }}" for c in frame.columns))
if st.button("Xem trước", disabled=not selected):
    try:
        st.markdown(f"**Đến:** {selected[0][email_col]}")
        st.markdown(f"**Tiêu đề:** {render_template(subject, selected[0], list(frame.columns))}")
        st.text(render_template(body, selected[0], list(frame.columns)))
    except Exception as exc:
        st.error(f"Không thể tạo bản xem trước: {exc}")

files = st.file_uploader("File đính kèm", accept_multiple_files=True, key="attachments")
attachments = [(f.name, f.getvalue()) for f in files]
if attachments:
    st.caption(" · ".join(f"{name} ({len(content)/1024:.1f} KB)" for name, content in attachments))
    for name, content in attachments:
        if not content or len(content) > MAX_ATTACHMENT:
            st.error(f"{name} rỗng hoặc vượt 10 MB.")
if st.session_state.mode == "Test":
    test_email = st.text_input("Email nhận thử", key="test_email")
else:
    test_email = ""
    st.warning("Live Mode sẽ gửi email riêng đến những người nhận đã chọn.")

job = st.session_state.get("job")
busy = bool(job and not job["done"])
allowed = bool(selected and config.ready and not busy and
               (st.session_state.mode == "Test" or live_confirmed) and
               all(content and len(content) <= MAX_ATTACHMENT for _, content in attachments))
with st.form("confirmation"):
    confirmation = st.checkbox("Tôi xác nhận gửi đến email thử nghiệm." if st.session_state.mode == "Test"
                               else f"Tôi xác nhận gửi thật đến {len(selected)} người nhận.")
    start = st.form_submit_button("Gửi email", type="primary", disabled=not allowed)
    retry = st.form_submit_button("Gửi lại lỗi", disabled=not allowed or st.session_state.mode != "Live")
    new_campaign = st.form_submit_button("Gửi lại tất cả · chiến dịch mới", disabled=not allowed)
if start or retry or new_campaign:
    if not confirmation:
        st.error("Vui lòng xác nhận trước khi gửi.")
    elif st.session_state.mode == "Test" and not test_email:
        st.error("Cần nhập email nhận thử.")
    else:
        if new_campaign:
            st.session_state.campaign = uuid.uuid4().hex[:12]
        campaign = st.session_state.campaign
        launch(dict(db_path=DB_PATH, campaign=campaign, rows=selected, columns=list(frame.columns),
                    email_col=email_col, subject_template=subject, body_template=body,
                    attachments=attachments, config=config, mode=st.session_state.mode,
                    test_email=test_email, retry_failed=retry))

if st.button("Reset giao diện", disabled=busy):
    reset()
st.divider()
st.subheader("Kết quả gửi")
st.caption(f"Campaign ID: {st.session_state.campaign}")
results_panel(st.session_state.campaign, st.session_state.mode,
              1 if st.session_state.mode == "Test" else len(selected))
