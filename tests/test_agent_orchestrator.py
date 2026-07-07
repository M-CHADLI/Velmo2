import time
from unittest.mock import MagicMock, patch
from agent.agent import VelmoAgent
from agent.schema import VelmoResponse
from guardrails.schema import GuardDecision


def test_process_message_allowed_flow():
    """Test full allowed message flow: input -> memory -> kimi -> output -> store."""
    # Mocks
    classifier = MagicMock()
    classifier.classify.return_value = "legitimate"

    llm = MagicMock()
    llm.invoke.return_value = "Your order 4490 is in transit."

    # Create agent
    agent = VelmoAgent(classifier=classifier, llm=llm)

    # Process message
    response = agent.process_message("u-test", "What's the status of order 4490?")

    # Assertions
    assert isinstance(response, VelmoResponse)
    assert response.allowed is True
    assert "4490" in response.message or "transit" in response.message
    assert response.turn_number == 1
    assert response.latency_ms > 0


def test_process_message_input_blocked():
    """Test input guard blocking."""
    classifier = MagicMock()
    llm = MagicMock()

    agent = VelmoAgent(classifier=classifier, llm=llm)

    # Hate message
    response = agent.process_message("u-test", "Tous les etrangers sont des sous-etres.")

    assert response.allowed is False
    assert response.guard_decision is not None
    assert response.guard_decision.category == "hate"
    assert "Je ne peux pas traiter" in response.message


def test_process_message_output_blocked():
    """Test output guard blocking PII."""
    classifier = MagicMock()
    classifier.classify.return_value = "legitimate"

    llm = MagicMock()
    # LLM returns PII (credit card)
    llm.invoke.return_value = "Your card is 4111 1111 1111 1111, expiry 04/27."

    agent = VelmoAgent(classifier=classifier, llm=llm)
    response = agent.process_message("u-test", "What's my payment method?")

    assert response.allowed is False
    assert response.guard_decision is not None
    assert response.guard_decision.category == "pii"
