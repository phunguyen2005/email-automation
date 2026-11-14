import smtplib

from services.database_service import history
from services.email_service import SMTPConfig, build_message, send_batch


CONFIG = SMTPConfig("smtp.example.com", 587, "user", "secret", "user@example.com")
ROWS = [{"name": "An", "email": "an@example.com"}]


class FakeSMTP:
    instances = []
    error = None

    def __init__(self, host, port, timeout):
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def starttls(self, context):
        pass

    def login(self, username, password):
        if FakeSMTP.error == "auth":
            raise smtplib.SMTPAuthenticationError(535, b"bad")

    def send_message(self, message):
        if FakeSMTP.error == "timeout":
            raise TimeoutError()
        self.messages.append(message)
        return {}


def run(tmp_path, mode="Live", campaign="c1", retry=False):
    return send_batch(str(tmp_path / "db.sqlite3"), campaign, ROWS, ["name", "email"],
                      "email", "Hi {{ name }}", "Chào {{ name }}", [("a.txt", b"hello")],
                      CONFIG, mode, test_email="tester@example.com", retry_failed=retry,
                      smtp_factory=FakeSMTP)


def test_attachment_and_success(tmp_path):
    FakeSMTP.error = None
    result = run(tmp_path)
    assert result[0][1] == "Sent"
    assert list(FakeSMTP.instances[-1].messages[0].iter_attachments())[0].get_content() == b"hello"
    assert run(tmp_path)[0][1] == "Skipped"


def test_auth_failure_and_retry(tmp_path):
    FakeSMTP.error = "auth"
    assert run(tmp_path)[0][1] == "Failed"
    FakeSMTP.error = None
    assert run(tmp_path, retry=True)[0][1] == "Sent"


def test_timeout_unknown(tmp_path):
    FakeSMTP.error = "timeout"
    assert run(tmp_path)[0][1] == "Unknown"
    FakeSMTP.error = None
    assert run(tmp_path, retry=True)[0][1] == "Skipped"


def test_mode_does_not_send_to_real_recipient(tmp_path):
    FakeSMTP.error = None
    assert run(tmp_path, mode="Test")[0][1] == "Sent"
    assert FakeSMTP.instances[-1].messages[0]["To"] == "tester@example.com"
    assert history(str(tmp_path / "db.sqlite3"), "c1", "Live") == []
    assert run(tmp_path, campaign="new")[0][1] == "Sent"
