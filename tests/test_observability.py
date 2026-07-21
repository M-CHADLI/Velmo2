"""Observability (LangSmith) must be fail-safe.

These tests force the disabled state via monkeypatch so they pass regardless
of the ambient .env (tracing may be enabled on the developer machine).
"""
import velmo.observability.tracing as tracing
from velmo.observability import trace_run


def test_is_enabled_returns_bool():
    assert isinstance(tracing.is_enabled(), bool)


def test_trace_run_is_noop_when_disabled(monkeypatch):
    """trace_run yields a usable handle and never raises when tracing is off."""
    monkeypatch.setattr(tracing, "_CONFIGURED", True)
    monkeypatch.setattr(tracing, "_ENABLED", False)
    with trace_run("unit_test", foo="bar") as run:
        run.log_score("some_metric", 1.0)
        run.log_score("with_comment", 0.0, comment="ok")
    # config is empty when disabled -> safe to spread into invoke(config=...)
    assert run.config == {}


def test_log_score_accepts_int_and_float(monkeypatch):
    monkeypatch.setattr(tracing, "_CONFIGURED", True)
    monkeypatch.setattr(tracing, "_ENABLED", False)
    with trace_run("unit_test") as run:
        run.log_score("int_metric", 5)
        run.log_score("float_metric", 3.14)
    assert run.config == {}


def test_trace_run_builds_config_when_enabled(monkeypatch):
    """When enabled, config carries run_name/tags/metadata/callbacks.

    Client is nulled so the score flush is a safe no-op (no network call)."""
    monkeypatch.setattr(tracing, "_CONFIGURED", True)
    monkeypatch.setattr(tracing, "_ENABLED", True)
    monkeypatch.setattr(tracing, "_client", None)
    tracing.set_user_context("u-test", "conv-1")
    with trace_run("guardrail_classifier") as run:
        run.log_score("blocked", 1.0, comment="hate")
        cfg = run.config
    assert cfg["run_name"] == "guardrail_classifier"
    assert "component:guardrail_classifier" in cfg["tags"]
    assert "user:u-test" in cfg["tags"]
    assert cfg["metadata"]["user_id"] == "u-test"
    assert cfg["metadata"]["conversation_id"] == "conv-1"
    assert cfg["callbacks"]  # RunCollectorCallbackHandler present
