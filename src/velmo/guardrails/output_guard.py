from .rules import match_output_pii
from .schema import GuardDecision, SAFE_MESSAGE


def check_output(response: str) -> GuardDecision:
    """Scan regex PII sur la réponse LLM. Bloque la réponse entière si PII."""
    hit = match_output_pii(response)
    if hit is not None:
        category, reason = hit
        return GuardDecision(
            allowed=False,
            category=category,
            where="output",
            safe_message=SAFE_MESSAGE,
            reason=reason,
        )
    return GuardDecision(allowed=True, category="legitimate", where="output")
