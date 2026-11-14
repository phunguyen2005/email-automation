import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from .database_service import claim, finish
from .data_service import EMAIL_RE
from .template_service import render_template

MAX_ATTACHMENT = 10 * 1024 * 1024
MAX_MESSAGE = 20 * 1024 * 1024


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    security: str = "starttls"

    @property
    def ready(self):
        return bool(self.host and self.username and self.password and self.from_email and self.security in {"starttls", "ssl"})


def build_message(sender, recipient, subject, body, attachments):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    total = len(body.encode("utf-8"))
    for name, content in attachments:
        if not content or len(content) > MAX_ATTACHMENT:
            raise ValueError(f"Tệp {name} rỗng hoặc vượt 10 MB.")
        total += len(content)
        if total > MAX_MESSAGE:
            raise ValueError("Tổng nội dung và tệp đính kèm vượt 20 MB.")
        message.add_attachment(content, maintype="application", subtype="octet-stream", filename=name)
    return message


def smtp_send(config: SMTPConfig, message, smtp_factory=None):
    if not config.ready:
        raise ValueError("Cấu hình SMTP chưa đầy đủ.")
    factory = smtp_factory or (smtplib.SMTP_SSL if config.security == "ssl" else smtplib.SMTP)
    with factory(config.host, config.port, timeout=20) as smtp:
        if config.security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        smtp.login(config.username, config.password)
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def send_batch(db_path, campaign, rows, columns, email_col, subject_template, body_template,
               attachments, config, mode, test_email="", retry_failed=False, on_progress=None,
               smtp_factory=None):
    if mode not in {"Test", "Live"}:
        raise ValueError("Chế độ gửi không hợp lệ.")
    if mode == "Test" and not EMAIL_RE.fullmatch(test_email.strip()):
        raise ValueError("Email nhận thử không hợp lệ.")
    targets = rows[:1] if mode == "Test" else rows
    outcome = []
    for row in targets:
        original = str(row[email_col]).strip()
        recipient = test_email.strip() if mode == "Test" else original
        key = recipient.casefold() if mode == "Test" else original.casefold()
        try:
            subject = render_template(subject_template, row, columns)
            body = render_template(body_template, row, columns)
            message = build_message(config.from_email, recipient, subject, body, attachments)
        except Exception as exc:
            outcome.append((recipient, "Invalid", str(exc)))
            if on_progress:
                on_progress(outcome)
            continue
        if not claim(db_path, campaign, key, recipient, subject, mode, retry_failed):
            outcome.append((recipient, "Skipped", "Đã xử lý trong chiến dịch này."))
            if on_progress:
                on_progress(outcome)
            continue
        try:
            smtp_send(config, message, smtp_factory)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused, ValueError) as exc:
            status = "Failed"
            error = type(exc).__name__
        except (OSError, smtplib.SMTPException) as exc:
            status = "Unknown"
            error = type(exc).__name__ + ": trạng thái SMTP chưa xác định; không tự động gửi lại"
        else:
            status = "Sent"
            error = ""
        finish(db_path, campaign, key, mode, status, error)
        outcome.append((recipient, status, error))
        if on_progress:
            on_progress(outcome)
    return outcome
