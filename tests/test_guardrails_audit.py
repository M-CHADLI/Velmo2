from unittest.mock import MagicMock
from velmo.guardrails.audit import write_log
from velmo.guardrails.schema import GuardDecision


def _fake_db():
    db = MagicMock()
    cur = MagicMock()
    # support du context manager `with conn.cursor() as cur:`
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db.connect.return_value = conn
    return db, conn, cur


def test_write_log_inserts_row():
    db, conn, cur = _fake_db()
    d = GuardDecision(allowed=False, category="hate", where="input",
                      reason="classifier", latency_ms=42)
    write_log("u-eval", d, db=db)
    assert cur.execute.call_count == 1
    conn.commit.assert_called_once()


def test_write_log_never_raises_on_db_error():
    db = MagicMock()
    db.connect.side_effect = RuntimeError("db down")
    d = GuardDecision(allowed=True, category="legitimate", where="input")
    # ne doit pas lever
    write_log("u-eval", d, db=db)
