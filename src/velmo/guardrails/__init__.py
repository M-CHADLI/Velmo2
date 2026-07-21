"""Velmo 2.0 Guardrails Package.

Implements input/output security guards for Velmo 2.0:
1. Input Guard: Detects harmful content (hate, violence, sexual, prompt injection, secret leak, out-of-scope).
2. Output Guard: Ensures output safety before delivery to the user.
3. Kimi Classifier: Uses Kimi 2.6 via LangChain to classify content risk category.
4. Audit Logging: PostgreSQL guardrail_log table tracks all decisions with latency metrics.
5. LangFuse Integration: CallbackHandler auto-instruments Kimi classifier calls for observability.
"""

from .manager import GuardrailManager
from .schema import GuardDecision, SAFE_MESSAGE

__all__ = [
    "GuardrailManager",
    "GuardDecision",
    "SAFE_MESSAGE",
]
