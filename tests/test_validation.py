import io

import pandas as pd
import pytest

from services.data_service import read_dataset, validate


def test_csv_and_unicode():
    data = "name,email\nNguyễn, user@example.com \n".encode("utf-8-sig")
    result = validate(read_dataset("list.csv", data))
    assert result.loc[0, "Trạng thái dữ liệu"] == "Hợp lệ"
    assert result.loc[0, "email"] == "user@example.com"


def test_xlsx():
    stream = io.BytesIO()
    pd.DataFrame({"name": ["An"], "Email": ["an@example.com"]}).to_excel(stream, index=False)
    assert len(read_dataset("list.xlsx", stream.getvalue())) == 1


def test_missing_column():
    with pytest.raises(ValueError, match="Email"):
        validate(pd.DataFrame({"name": ["An"]}))


def test_invalid_and_duplicate():
    result = validate(pd.DataFrame({"email": ["bad", "a@example.com", "A@example.com", ""]}))
    assert result["Trạng thái dữ liệu"].tolist() == [
        "Email không hợp lệ", "Hợp lệ", "Trùng email", "Thiếu email"]
