# Chantier 3: Evaluation & MLOps

## Objectif

Évaluer la qualité de Velmo (métriques, benchmarks) et gérer le cycle de vie des modèles (versioning, A/B testing, auto-deploy/rollback).

---

## Composants Principaux

### Evaluation (Chantier 3.1)

Mesurer et monitorer:

1. **Judge Quality**
   - Confidence moyenne (target: > 0.85)
   - Hallucination rate (target: < 5%)
   - Recall@5 on fact extraction

2. **Retriever Quality**
   - Precision/Recall (semantic search)
   - NDCG (ranking metrics)
   - Cosine similarity distribution

3. **LLM Response Quality**
   - Relevance (LLM-as-judge)
   - Coherence, factuality
   - Latency SLA (< 2000ms)

4. **Memory Quality**
   - Fact version drift tracking
   - Contradiction detection
   - Staleness metrics

### Observability (Chantier 3.2)

Monitorer en temps réel via **LangSmith**:

1. **Request Tracing**
   - All LangChain calls traced
   - Token usage per component
   - Latency breakdown

2. **Metrics Dashboard**
   - Judge confidence trends
   - Token consumption trends
   - Cost per user/day
   - Error rates

3. **Alerting**
   - Judge confidence < 0.8 → Alert
   - Latency > 3000ms → Alert
   - Cost spike → Alert

### MLOps (Chantier 3.3)

Gérer déploiement et versioning:

1. **Model Registry** (MLflow)
   - Track Kimi versions
   - Embedding model versions
   - Guardrails model versions

2. **Version Control**
   - Config as code (git)
   - CLAUDE.md tracks architecture changes
   - A/B test configurations

3. **CI/CD Pipeline**
   - Auto-test metrics on PR
   - Gate: judge_confidence_avg >= 0.85
   - Auto-deploy if passed
   - Auto-rollback if metric degrade

4. **Data Versioning** (DVC)
   - Track eval datasets
   - Version training data
   - Reproducible experiments

---

## Fichiers de Conception

- **01_METRICS.md** — Définition formelle des métriques
- **02_MLOPS.md** — CI/CD, versioning, deployment strategy
- **03_DIAGRAMMES.md** — Diagrams (Mermaid)

---

## Fichiers Schemas

```
schemas/
├── judge_evaluation.schema.json     — Judge quality metrics
├── retriever_evaluation.schema.json — Retrieval metrics
├── llm_evaluation.schema.json       — LLM output metrics
└── deployment_config.schema.json    — Model versions + configs
```

---

## Intégration avec Chantier 1 & 2

- **← Chantier 1**: Reçoit traces d'extraction du judge
- **← Chantier 2**: Reçoit logs d'audit pour compliance monitoring
- **→ CD Pipeline**: Décisions de deploy/rollback

---

## LangSmith Integration

```python
from langsmith import Client

client = Client()

# Get recent runs
runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='startTime > "2024-01-01"'
)

# Compute metrics
judge_confidences = [
    float(r.outputs.get("judge_confidence", 0))
    for r in runs
]

avg_confidence = sum(judge_confidences) / len(judge_confidences)

# Gate deployment
if avg_confidence < 0.85:
    print("❌ Judge confidence too low, blocking deploy")
    exit(1)
else:
    print(f"✅ Judge confidence {avg_confidence:.2f}, proceed")
```

---

## Quick Start

```python
from chantier_3_evals import EvaluationPipeline, MLOpsManager

# Evaluation
evaluator = EvaluationPipeline()
metrics = evaluator.evaluate_judge(test_cases)
print(f"Judge confidence: {metrics['avg_confidence']:.2f}")

# MLOps
mlops = MLOpsManager()
mlops.register_model(
    name="kimi-2.6",
    version="1.0",
    metrics=metrics
)
mlops.deploy_if_metrics_pass(threshold=0.85)
```

---

## Metrics Targets (SLA)

| Metric | Target | Critical |
|--------|--------|----------|
| judge_confidence_avg | > 0.85 | < 0.80 |
| judge_hallucination_rate | < 5% | > 10% |
| retriever_recall@5 | > 0.8 | < 0.7 |
| llm_latency_p95 | < 2000ms | > 3000ms |
| memory_staleness | < 20% | > 30% |
| audit_log_completeness | 100% | < 99.9% |

---

## Next: Read [01_METRICS.md](./01_METRICS.md)
