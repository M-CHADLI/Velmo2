import logging
import time
from .rules import match_input_rules
from .classifier import KimiClassifier
from .schema import GuardDecision, SAFE_MESSAGE, FORBIDDEN_INPUT_CATEGORIES

logger = logging.getLogger(__name__)


def check_input(message: str, classifier: KimiClassifier) -> GuardDecision:
    """Étage 1 règles (rapide) puis étage 2 classifieur Kimi (nuancé)."""
    start = time.perf_counter()

    # Étage 1 : règles déterministes
    hit = match_input_rules(message)
    if hit is not None:
        category, reason = hit
        return GuardDecision(
            allowed=False, category=category, where="input",
            safe_message=SAFE_MESSAGE, reason=reason,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    # Étage 2 : classifieur Kimi (retry interne, lève si KO)
    try:
        category = classifier.classify(message)
    except RuntimeError as e:
        # Fail-safe : bloquer si le classifieur est indisponible
        logger.error(f"Classifier indisponible, fail-safe BLOCK: {e}")
        return GuardDecision(
            allowed=False, category="classifier_error", where="input",
            safe_message=SAFE_MESSAGE, reason=str(e),
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    latency = int((time.perf_counter() - start) * 1000)
    if category in FORBIDDEN_INPUT_CATEGORIES:
        return GuardDecision(
            allowed=False, category=category, where="input",
            safe_message=SAFE_MESSAGE, reason="classifier", latency_ms=latency,
        )
    return GuardDecision(
        allowed=True, category="legitimate", where="input",
        reason="classifier", latency_ms=latency,
    )
