"""Suite d'évaluation "qualité générale" : rejoue eval/quality_cases.jsonl.

Pour chaque cas, on pose la question à l'agent complet (mémoire + garde-fous +
LLM) et on vérifie que la réponse contient bien le texte attendu.

Usage:
    uv run python scripts/eval_quality.py
"""
import json
import logging
import sys
import time
from typing import Any

from eval_memory import normalize_text

from velmo.agent.agent import VelmoAgent
from velmo.config import load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_cases(path: str) -> list[dict]:
    """Lit un fichier .jsonl et retourne la liste des cas."""
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def run_eval(cases_file: str = "eval/quality_cases.jsonl") -> dict[str, Any]:
    """Rejoue tous les cas de qualité et retourne un résumé des scores."""
    cases = load_cases(cases_file)
    agent = VelmoAgent(settings=load_settings())

    results = []
    passed_count = 0
    total_latency_ms = 0

    print("\n" + "=" * 80)
    print(f"RUNNING QUALITY EVALUATION HARNESS: {len(cases)} cases")
    print("=" * 80)

    for case in cases:
        case_id = case["id"]
        user_id = case["user_id"]
        question = case["question"]
        expected = case["expected_substring"]

        start_time = time.perf_counter()
        response = agent.process_message(user_id=user_id, message=question)
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        total_latency_ms += latency_ms

        passed = normalize_text(expected) in normalize_text(response.message)
        if passed:
            passed_count += 1

        status = "PASS" if passed else "FAIL"
        print(f"\n[Test Case] {case_id} - {status}")
        print(f"  Question: {question}")
        print(f"  Réponse:  {response.message}")
        print(f"  Attendu (sous-chaîne): '{expected}'")

        results.append({
            "id": case_id,
            "passed": passed,
            "latency_ms": latency_ms,
        })

    success_rate = (passed_count / len(cases)) * 100 if cases else 0
    avg_latency = (total_latency_ms / len(cases)) if cases else 0

    print("\n" + "=" * 80)
    print("QUALITY EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Cases:  {len(cases)}")
    print(f"Passed:       {passed_count}")
    print(f"Failed:       {len(cases) - passed_count}")
    print(f"Success Rate: {success_rate:.2f}%")
    print(f"Avg Latency:  {avg_latency:.2f} ms")
    print("=" * 80)

    return {
        "total": len(cases),
        "passed": passed_count,
        "success_rate": success_rate,
        "avg_latency_ms": avg_latency,
        "results": results,
    }


if __name__ == "__main__":
    cases_file = sys.argv[1] if len(sys.argv) > 1 else "eval/quality_cases.jsonl"
    run_eval(cases_file)
