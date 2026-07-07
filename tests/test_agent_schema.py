# tests/test_agent_schema.py
from agent.schema import VelmoResponse
from guardrails.schema import GuardDecision

def test_velmo_response_allowed():
    """Test VelmoResponse for allowed message."""
    resp = VelmoResponse(
        allowed=True,
        message="Your order 4490 is in transit.",
        guard_decision=None,
        memory_context={"short_term": [{"role": "user", "content": "Status?"}]},
        turn_number=1,
        latency_ms=523
    )
    assert resp.allowed is True
    assert resp.message == "Your order 4490 is in transit."
    assert resp.turn_number == 1

def test_velmo_response_blocked():
    """Test VelmoResponse for blocked message."""
    decision = GuardDecision(
        allowed=False,
        category="hate",
        where="input",
        safe_message="Je ne peux pas traiter cette demande.",
        reason="hate speech detected",
        latency_ms=45
    )
    resp = VelmoResponse(
        allowed=False,
        message="Je ne peux pas traiter cette demande.",
        guard_decision=decision,
        memory_context={},
        turn_number=1,
        latency_ms=48
    )
    assert resp.allowed is False
    assert resp.guard_decision.category == "hate"
