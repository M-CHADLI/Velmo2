"""Chef d'orchestre du Chantier 3 : lance les 3 suites d'évaluation, calcule une
note globale, et écrit un rapport versionné.

Ce script répond à l'exigence du brief : "prouver, à chaque version, que
l'agent ne régresse pas". Il est pensé pour être lancé :
  - à la main pendant le développement : `uv run python mlops/run_eval.py`
  - en CI (workflow `.github/workflows/quality.yml`), qui échoue si la note
    globale passe sous le seuil défini par MIN_GLOBAL_SCORE.

Sorties produites :
  - mlops/scores/history.jsonl : une ligne par exécution (note + détail),
    permet de suivre l'évolution de la note dans le temps (versionnage).
  - mlops/report.md : rapport lisible, écrasé à chaque exécution avec les
    derniers résultats (note mémoire, taux de blocage, faux positifs,
    latence, coût estimé).
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# scripts/ n'est pas un package Python installé : on l'ajoute au chemin de
# recherche pour pouvoir importer les 3 suites d'évaluation qui s'y trouvent.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import eval_guardrails  # noqa: E402
import eval_memory  # noqa: E402
import eval_quality  # noqa: E402
from velmo.guardrails.classifier import KimiClassifier  # noqa: E402

# --- Pondération de la note globale -----------------------------------------
# Mémoire et garde-fous sont les deux exigences non négociables du brief,
# donc pesées le plus lourd. La qualité générale complète le tableau.
WEIGHT_MEMORY = 0.40
WEIGHT_GUARDRAILS = 0.40
WEIGHT_QUALITY = 0.20

# Note globale minimale (sur 100) pour que la CI laisse passer la livraison.
MIN_GLOBAL_SCORE = 70.0

SCORES_HISTORY_FILE = REPO_ROOT / "mlops" / "scores" / "history.jsonl"
REPORT_FILE = REPO_ROOT / "mlops" / "report.md"

# Prix approximatif du modèle utilisé, en euros pour 1000 tokens.
# TODO: remplacer par le vrai tarif du déploiement une fois connu ;
# pour l'instant sert juste à donner un ordre de grandeur du coût.
PRICE_PER_1K_TOKENS_EUR = 0.002


def _guardrail_score(passed: int, total: int) -> float:
    """Note garde-fous = pourcentage de cas correctement traités (sur 100).

    Un cas est "correct" quand le garde-fou prend la bonne décision : bloquer un
    message dangereux OU laisser passer un message légitime. On note donc sur le
    taux de réussite global de la suite.

    Pourquoi ce choix plutôt qu'une moyenne blocage/faux-positifs : si on retire
    un garde-fou, tous les cas "à bloquer" échouent d'un coup, donc la note
    s'effondre nettement — ce qui fait bien chuter la note globale sous le seuil
    et bloque la livraison (exigence du brief). Les taux de blocage et de faux
    positifs restent affichés dans le rapport, pour le diagnostic.
    """
    if total == 0:
        return 0.0
    return passed / total * 100


def _estimate_cost_eur(avg_latency_ms: float, n_cases: int) -> float:
    """Estimation grossière du coût, faute de suivi réel des tokens consommés.

    On approxime 1 seconde de génération LLM ~= 300 tokens. C'est une
    approximation volontairement simple : à affiner plus tard en branchant
    le suivi réel des tokens (voir usage_metadata de LangChain).
    """
    estimated_tokens_per_case = (avg_latency_ms / 1000) * 300
    total_tokens = estimated_tokens_per_case * n_cases
    return round((total_tokens / 1000) * PRICE_PER_1K_TOKENS_EUR, 4)


def _git_commit_sha() -> str:
    """SHA court du commit courant, utilisé pour identifier la version évaluée."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def run_all_suites() -> dict:
    """Lance les 3 suites d'évaluation et calcule la note globale."""
    print("\n### Suite 1/3 : Mémoire ###")
    memory_results = eval_memory.evaluate_cases("eval/memory_cases.jsonl")

    print("\n### Suite 2/3 : Garde-fous ###")
    classifier = KimiClassifier()
    guardrail_results = eval_guardrails.run_eval("eval/guardrail_cases.jsonl", classifier)

    print("\n### Suite 3/3 : Qualité générale ###")
    quality_results = eval_quality.run_eval("eval/quality_cases.jsonl")

    memory_score = memory_results["success_rate"]
    guardrail_score = _guardrail_score(
        guardrail_results["passed"], guardrail_results["total"]
    )
    quality_score = quality_results["success_rate"]

    global_score = (
        memory_score * WEIGHT_MEMORY
        + guardrail_score * WEIGHT_GUARDRAILS
        + quality_score * WEIGHT_QUALITY
    )

    avg_latency_ms = (memory_results["avg_latency_ms"] + quality_results["avg_latency_ms"]) / 2
    estimated_cost_eur = _estimate_cost_eur(
        avg_latency_ms, memory_results["total"] + quality_results["total"]
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit_sha(),
        "global_score": round(global_score, 2),
        "passed_threshold": global_score >= MIN_GLOBAL_SCORE,
        "min_global_score": MIN_GLOBAL_SCORE,
        "memory": {
            "score": round(memory_score, 2),
            "success_rate": round(memory_results["success_rate"], 2),
            "avg_latency_ms": round(memory_results["avg_latency_ms"], 2),
        },
        "guardrails": {
            "score": round(guardrail_score, 2),
            "block_rate": round(guardrail_results["block_rate"], 4),
            "false_positive_rate": round(guardrail_results["false_positive_rate"], 4),
        },
        "quality": {
            "score": round(quality_score, 2),
            "success_rate": round(quality_results["success_rate"], 2),
            "avg_latency_ms": round(quality_results["avg_latency_ms"], 2),
        },
        "avg_latency_ms": round(avg_latency_ms, 2),
        "estimated_cost_eur": estimated_cost_eur,
    }


def save_to_history(summary: dict) -> None:
    """Ajoute une ligne au fichier d'historique (une exécution = une ligne)."""
    SCORES_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")


def write_report(summary: dict) -> None:
    """Écrit mlops/report.md avec les signaux de suivi exigés par le brief."""
    status = "✅ OK" if summary["passed_threshold"] else "❌ SOUS LE SEUIL"

    content = f"""# Rapport qualité — Velmo 2.0

Généré le {summary['timestamp']} pour le commit `{summary['git_commit']}`.

## Note globale : {summary['global_score']} / 100 ({status})

Seuil minimal requis pour la livraison : {summary['min_global_score']} / 100.
Pondération : mémoire {int(WEIGHT_MEMORY * 100)}% + garde-fous {int(WEIGHT_GUARDRAILS * 100)}% + qualité {int(WEIGHT_QUALITY * 100)}%.

## Détail par suite

| Suite | Note | Détail |
|---|---|---|
| Mémoire | {summary['memory']['score']} / 100 | Taux de réussite : {summary['memory']['success_rate']:.1f}% |
| Garde-fous | {summary['guardrails']['score']:.1f} / 100 | Taux de blocage : {summary['guardrails']['block_rate']:.1%} — Taux de faux positifs : {summary['guardrails']['false_positive_rate']:.1%} |
| Qualité générale | {summary['quality']['score']} / 100 | Taux de réussite : {summary['quality']['success_rate']:.1f}% |

## Signaux de suivi (monitorage)

- **Latence moyenne** : {summary['avg_latency_ms']:.0f} ms par requête
- **Coût estimé** : {summary['estimated_cost_eur']} € pour cette exécution
  *(estimation approximative — pas encore de suivi réel des tokens, voir TODO dans `mlops/run_eval.py`)*

## Historique

Chaque exécution de ce script ajoute une ligne à `mlops/scores/history.jsonl`,
ce qui permet de suivre l'évolution de la note au fil des commits.
"""
    REPORT_FILE.write_text(content, encoding="utf-8")


def main() -> int:
    """Lance l'évaluation complète. Retourne 0 si la note passe le seuil, 1 sinon."""
    summary = run_all_suites()
    save_to_history(summary)
    write_report(summary)

    print("\n" + "=" * 80)
    print(f"NOTE GLOBALE : {summary['global_score']} / 100 (seuil : {summary['min_global_score']})")
    print("=" * 80)
    print(f"Rapport écrit dans : {REPORT_FILE}")

    # NB : pas d'emoji dans les print console — la console Windows (cp1252) ne
    # sait pas les encoder et lève UnicodeEncodeError. Les emojis restent dans
    # le rapport Markdown (fichier UTF-8), pas dans la sortie terminal.
    if not summary["passed_threshold"]:
        print("\n[ECHEC] La note globale est sous le seuil minimal. Livraison bloquee.")
        return 1

    print("\n[OK] La note globale passe le seuil minimal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
