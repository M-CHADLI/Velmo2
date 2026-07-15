import json
import logging
from velmo.guardrails.input_guard import check_input
from velmo.guardrails.output_guard import check_output

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate_case(case: dict, classifier) -> bool:
    """Rejoue un cas et compare la décision à expected_action."""
    if case["where"] == "input":
        decision = check_input(case["message"], classifier)
    else:
        decision = check_output(case["message"])
    expected_allowed = case["expected_action"] == "allow"
    return decision.allowed == expected_allowed


def run_eval(path: str, classifier) -> dict:
    """Rejoue tout le jeu de cas et calcule blocage + faux positifs."""
    total = passed = 0
    toxic = toxic_blocked = 0
    legit = legit_blocked = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            ok = evaluate_case(case, classifier)
            total += 1
            passed += int(ok)

            if case["expected_action"] == "block":
                toxic += 1
                toxic_blocked += int(ok)
            else:
                legit += 1
                legit_blocked += int(not ok)  # légitime bloqué à tort

    return {
        "total": total,
        "passed": passed,
        "block_rate": toxic_blocked / toxic if toxic else 0.0,
        "false_positive_rate": legit_blocked / legit if legit else 0.0,
    }


if __name__ == "__main__":
    from velmo.guardrails.classifier import KimiClassifier
    results = run_eval("eval/guardrail_cases.jsonl", KimiClassifier())
    logger.info(f"Résultats garde-fous : {results}")
