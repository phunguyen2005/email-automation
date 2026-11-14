# Email Automation

Ứng dụng Streamlit một trang để kiểm tra danh sách Excel/CSV, soạn email cá nhân hóa và gửi từng email qua SMTP. Mặc định là **Test Mode**. Trạng thái **Sent** chỉ có nghĩa máy chủ SMTP đã chấp nhận thư, không xác nhận thư đến hộp nhận.

## Cài đặt trên Windows

Yêu cầu Python 3.11 trở lên. Trong PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Sửa `.env`: điền `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`. Với Gmail, bật xác minh hai bước và tạo **App Password** trong tài khoản Google; nhập App Password vào `SMTP_PASSWORD`. Không dùng mật khẩu đăng nhập thông thường. Có thể đổi `SMTP_HOST`, `SMTP_PORT` và `SMTP_SECURITY` (`starttls` hoặc `ssl`) cho nhà cung cấp khác.

```powershell
streamlit run app.py
```

Không commit `.env`. SQLite được tự tạo tại `data/email_automation.sqlite3`.

## Dữ liệu và cách dùng

Tải file `.xlsx` hoặc `.csv` tối đa 15 MB. Cần một cột `email` (không phân biệt chữ hoa/thường); các cột khác được giữ nguyên và dùng làm biến Jinja2, ví dụ `{{ name }}`. Với tên cột có dấu cách, dùng `{{ row["Họ tên"] }}`. Dataset thực tế chưa được cung cấp; `data/sample_dataset.csv` giả định các cột `name,email,score,group`, gồm dòng hợp lệ, sai định dạng và trùng để trình diễn.

Sau khi tải lên, lọc/tìm kiếm và đánh dấu người nhận. Soạn nội dung, xem trước, tải file đính kèm rồi xác nhận gửi. Test Mode chỉ gửi một thư mẫu đến địa chỉ thử nghiệm. Live Mode gửi cho các dòng hợp lệ đã chọn. Mỗi tệp đính kèm tối đa 10 MB, tổng nội dung và tệp tối đa 20 MB; giới hạn thực tế của nhà cung cấp có thể thấp hơn.

Campaign ID duy trì trong phiên trình duyệt. SQLite ngăn gửi lại email đã được SMTP chấp nhận, kể cả khi tải lại trang hoặc khởi động lại ứng dụng, miễn dùng cùng Campaign ID. Nút **Gửi lại lỗi** chỉ thử lại trạng thái Failed; trạng thái Unknown cần kiểm tra thủ công vì SMTP có thể đã nhận thư. **Gửi lại tất cả** tạo chiến dịch mới sau xác nhận. Reset chỉ xóa trạng thái giao diện, không xóa lịch sử SQLite.

## Kiểm thử

```powershell
python -m pytest -q
```

Kiểm thử dùng SMTP giả, không gửi email thật. Chưa xác minh gửi qua Gmail do không có thông tin xác thực.
