import io
import re

import pandas as pd

EMAIL_RE = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]*[A-Z0-9])?)+$", re.I)


def read_dataset(name: str, content: bytes) -> pd.DataFrame:
    if not content or len(content) > 15 * 1024 * 1024:
        raise ValueError("Tệp rỗng hoặc vượt giới hạn 15 MB.")
    suffix = name.lower().rsplit(".", 1)[-1]
    if suffix == "xlsx":
        frame = pd.read_excel(io.BytesIO(content), engine="openpyxl", dtype=str, keep_default_na=False)
    elif suffix == "csv":
        last_error = None
        for encoding in ("utf-8-sig", "utf-8", "cp1258"):
            try:
                frame = pd.read_csv(io.BytesIO(content), encoding=encoding, dtype=str, keep_default_na=False)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        else:
            raise ValueError("Không đọc được mã hóa CSV.") from last_error
    else:
        raise ValueError("Chỉ hỗ trợ .xlsx hoặc .csv.")
    if frame.empty:
        raise ValueError("Tệp không có bản ghi.")
    if frame.columns.duplicated().any():
        raise ValueError("Tên cột bị trùng.")
    return frame.fillna("").astype(str)


def email_column(frame: pd.DataFrame) -> str:
    matches = [c for c in frame.columns if c.strip().casefold() in {"email", "e-mail", "email address", "địa chỉ email"}]
    if not matches:
        raise ValueError("Thiếu cột Email bắt buộc.")
    return matches[0]


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    column = email_column(frame)
    result = frame.copy()
    result[column] = result[column].astype(str).str.strip()
    seen = set()
    statuses = []
    for value in result[column]:
        key = value.casefold()
        if not value:
            status = "Thiếu email"
        elif not EMAIL_RE.fullmatch(value):
            status = "Email không hợp lệ"
        elif key in seen:
            status = "Trùng email"
        else:
            status = "Hợp lệ"
            seen.add(key)
        statuses.append(status)
    result.insert(0, "Trạng thái dữ liệu", statuses)
    result.insert(0, "Chọn", [s == "Hợp lệ" for s in statuses])
    return result
