from pydantic import BaseModel
from guardrails.schema import GuardDecision

class VelmoResponse(BaseModel):
    """Unified response from VelmoAgent.process_message()."""
    allowed: bool
    message: str
    guard_decision: GuardDecision | None
    memory_context: dict
    turn_number: int
    latency_ms: int
