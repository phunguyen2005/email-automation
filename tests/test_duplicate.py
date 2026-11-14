from services.database_service import claim, finish, history


def test_persistent_dedup_and_failed_retry(tmp_path):
    path = str(tmp_path / "history.db")
    assert claim(path, "campaign", "a@example.com", "a@example.com", "Hi", "Live")
    finish(path, "campaign", "a@example.com", "Live", "Sent")
    assert not claim(path, "campaign", "a@example.com", "a@example.com", "Hi", "Live")
    assert not claim(path, "campaign", "a@example.com", "a@example.com", "Hi", "Live", True)
    assert claim(path, "new", "a@example.com", "a@example.com", "Hi", "Live")
    finish(path, "new", "a@example.com", "Live", "Failed", "Authentication failed")
    assert claim(path, "new", "a@example.com", "a@example.com", "Hi", "Live", True)
    assert history(path, "campaign", "Live")[0][4] == "Sent"


def test_unknown_never_retried(tmp_path):
    path = str(tmp_path / "history.db")
    assert claim(path, "campaign", "a@example.com", "a@example.com", "Hi", "Live")
    finish(path, "campaign", "a@example.com", "Live", "Unknown")
    assert not claim(path, "campaign", "a@example.com", "a@example.com", "Hi", "Live", True)
