from pydantic import BaseModel

SAFE_MESSAGE = (
    "Je ne peux pas traiter cette demande. "
    "Je suis l'assistant du support Velmo — reformulez et je vous aide avec plaisir."
)

FORBIDDEN_INPUT_CATEGORIES = {
    "hate", "violence", "sexual",
    "prompt_injection", "secret_leak", "out_of_scope",
}


class GuardDecision(BaseModel):
    """Résultat unique d'un contrôle garde-fou (entrée ou sortie)."""
    allowed: bool
    category: str
    where: str  # "input" | "output"
    safe_message: str | None = None
    reason: str = ""
    latency_ms: int = 0
