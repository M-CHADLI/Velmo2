from guardrails.schema import GuardDecision, SAFE_MESSAGE, FORBIDDEN_INPUT_CATEGORIES


def test_guard_decision_defaults():
    """Test that GuardDecision objects have correct default values."""
    d = GuardDecision(allowed=True, category="legitimate", where="input")
    assert d.allowed is True
    assert d.safe_message is None  # Optional field defaults to None
    assert d.reason == ""  # reason field has empty string default
    assert d.latency_ms == 0  # latency_ms field has zero default


def test_safe_message_is_generic():
    """Test that SAFE_MESSAGE contains the required Velmo support reference."""
    assert "support Velmo" in SAFE_MESSAGE


def test_forbidden_categories_complete():
    """Test that FORBIDDEN_INPUT_CATEGORIES contains exactly the required categories."""
    assert FORBIDDEN_INPUT_CATEGORIES == {
        "hate", "violence", "sexual",
        "prompt_injection", "secret_leak", "out_of_scope",
    }
