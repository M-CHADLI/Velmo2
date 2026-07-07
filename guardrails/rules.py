import re

# Motifs d'injection de prompt (formulations typées, insensibles à la casse)
_INJECTION_PATTERNS = [
    r"ignore[sz]?\s+tes\s+instructions",
    r"oublie[sz]?\s+tes\s+(consignes|instructions|regles)",
    r"tu\s+n'?as\s+plus\s+de\s+regles",
    r"developer\s+mode",
    r"(revele|affiche|montre)[sz]?\s+(ton|le)\s+(prompt|systeme)",
    r"prompt\s+systeme\s+initial",
]

# Motifs de fuite de secrets / config interne
_SECRET_PATTERNS = [
    r"cle\s+(?:d')?api",
    r"mot\s+de\s+passe\s+de\s+la\s+base",
    r"variables?\s+d'?environnement",
    r"tokens?\s+internes?",
    r"secret\s+de\s+configuration",
]

# Motifs PII en sortie
_CREDIT_CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9]{4}[ ]?){2,}[A-Z0-9]{1,4}\b")
_PASSWORD = re.compile(r"mot\s+de\s+passe[^:=]*(?:[:=est]+\s+\S+)", re.IGNORECASE)

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_SECRET_RE = [re.compile(p, re.IGNORECASE) for p in _SECRET_PATTERNS]


def match_input_rules(message: str) -> tuple[str, str] | None:
    """Détecte injection de prompt ou fuite de secret via motifs. None si rien."""
    for rx in _INJECTION_RE:
        if rx.search(message):
            return ("prompt_injection", f"rule:{rx.pattern}")
    for rx in _SECRET_RE:
        if rx.search(message):
            return ("secret_leak", f"rule:{rx.pattern}")
    return None


def match_output_pii(text: str) -> tuple[str, str] | None:
    """Détecte carte bancaire / IBAN / mot de passe en sortie. None si rien."""
    if _PASSWORD.search(text):
        return ("pii", "rule:password")
    if _IBAN.search(text):
        return ("pii", "rule:iban")
    if _CREDIT_CARD.search(text):
        return ("pii", "rule:credit_card")
    return None
