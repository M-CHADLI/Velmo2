"""Tests des fonctions de calcul de mlops/run_eval.py (pas d'appel LLM/DB ici)."""
import json

from mlops.run_eval import (
    MIN_GLOBAL_SCORE,
    _estimate_cost_eur,
    _guardrail_score,
    save_to_history,
    write_report,
)


def test_guardrail_score_all_passed():
    """Tous les cas correctement traités -> note maximale."""
    assert _guardrail_score(passed=37, total=37) == 100.0


def test_guardrail_score_none_passed():
    """Aucun cas correct -> note minimale."""
    assert _guardrail_score(passed=0, total=37) == 0.0


def test_guardrail_score_partial():
    """Réussite partielle -> note intermédiaire proportionnelle."""
    assert _guardrail_score(passed=18, total=36) == 50.0


def test_guardrail_score_empty_suite_is_zero():
    """Suite vide (division par zéro évitée) -> note nulle, pas d'erreur."""
    assert _guardrail_score(passed=0, total=0) == 0.0


def test_estimate_cost_eur_is_positive_and_scales_with_cases():
    cost_1_case = _estimate_cost_eur(avg_latency_ms=1000, n_cases=1)
    cost_10_cases = _estimate_cost_eur(avg_latency_ms=1000, n_cases=10)
    assert cost_1_case > 0
    assert cost_10_cases == round(cost_1_case * 10, 4)


def _sample_summary(global_score: float) -> dict:
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "git_commit": "abc1234",
        "global_score": global_score,
        "passed_threshold": global_score >= MIN_GLOBAL_SCORE,
        "min_global_score": MIN_GLOBAL_SCORE,
        "memory": {"score": 90.0, "success_rate": 90.0, "avg_latency_ms": 500.0},
        "guardrails": {"score": 95.0, "block_rate": 0.95, "false_positive_rate": 0.02},
        "quality": {"score": 80.0, "success_rate": 80.0, "avg_latency_ms": 400.0},
        "avg_latency_ms": 450.0,
        "estimated_cost_eur": 0.01,
    }


def test_write_report_creates_readable_file(tmp_path, monkeypatch):
    report_file = tmp_path / "report.md"
    monkeypatch.setattr("mlops.run_eval.REPORT_FILE", report_file)

    write_report(_sample_summary(global_score=85.0))

    content = report_file.read_text(encoding="utf-8")
    assert "85.0 / 100" in content
    assert "✅ OK" in content


def test_write_report_shows_failure_when_below_threshold(tmp_path, monkeypatch):
    report_file = tmp_path / "report.md"
    monkeypatch.setattr("mlops.run_eval.REPORT_FILE", report_file)

    write_report(_sample_summary(global_score=10.0))

    content = report_file.read_text(encoding="utf-8")
    assert "❌ SOUS LE SEUIL" in content


def test_save_to_history_appends_one_json_line_per_call(tmp_path, monkeypatch):
    history_file = tmp_path / "history.jsonl"
    monkeypatch.setattr("mlops.run_eval.SCORES_HISTORY_FILE", history_file)

    save_to_history(_sample_summary(global_score=85.0))
    save_to_history(_sample_summary(global_score=90.0))

    lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["global_score"] == 85.0
    assert json.loads(lines[1])["global_score"] == 90.0
