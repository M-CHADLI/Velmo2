# Chantier 3: Métriques Formelles & SLA

## Vue d'Ensemble

Chantier 3 mesure trois aspects de Velmo:

1. **Evaluation** — Qualité des composants (judge, retriever, LLM)
2. **Observability** — Tracing & dashboards en temps réel (LangSmith)
3. **MLOps** — Versioning, CI/CD gates, auto-deploy/rollback

---

## 1. Métriques Chantier 1: Mémoire

### 1.1 Judge Quality

**judge_confidence_avg**
- **Définition**: Average confidence score of extracted facts
- **Calcul**: Mean of fact.confidence across all facts per extraction
- **Target**: ≥ 0.85
- **Critical**: < 0.80
- **Mesure**: LangSmith (run output → judge_confidence field)
- **Frequency**: Every extraction (every 10 msgs)

```python
def calc_judge_confidence(extraction_metadata: list) -> float:
    """Average confidence per extraction round."""
    confidences = [m.judge_confidence for m in extraction_metadata]
    return sum(confidences) / len(confidences) if confidences else 0.0
```

**judge_hallucination_rate**
- **Définition**: % of facts that are factually incorrect or made up
- **Calcul**: Manual validation + feedback loop
  - Collect facts from 100 extractions
  - Have human annotators mark correct/incorrect
  - hallucination_rate = incorrect / total
- **Target**: < 5%
- **Critical**: > 10%
- **Frequency**: Weekly (sample of 100 recent extractions)

```python
def calc_hallucination_rate(feedback_runs: list) -> float:
    """Percentage of hallucinated facts based on human feedback."""
    incorrect = sum(1 for f in feedback_runs if f.score < 0.5)
    return incorrect / len(feedback_runs) if feedback_runs else 0.0
```

**judge_extraction_completeness**
- **Définition**: % of relevant facts actually extracted from messages
- **Calcul**: Recall metric
  - Gold standard: manually label key facts in 20 conversations
  - Judge extraction: use Kimi
  - Recall = facts_found / facts_total
- **Target**: ≥ 0.80
- **Critical**: < 0.70
- **Frequency**: Monthly (vs. labeled dataset)

---

### 1.2 Retriever Quality

**retriever_recall@5**
- **Définition**: If we need fact X, do top-5 results include it?
- **Calcul**: Recall@5 over test set
  - Query: natural language question
  - Expected facts: hand-labeled
  - Retrieved: top-5 from Pinecone
  - Recall = facts_found_in_top5 / facts_total
- **Target**: ≥ 0.80
- **Critical**: < 0.70
- **Frequency**: Weekly (100 test queries)

```python
def calc_retriever_recall_at_5(test_queries: list) -> float:
    """Calculate recall@5 for retriever."""
    total_relevant = 0
    total_found = 0
    
    for query in test_queries:
        results = vectorstore.similarity_search(query.text, k=5)
        result_ids = {r.metadata["fact_id"] for r in results}
        
        for relevant_id in query.expected_fact_ids:
            total_relevant += 1
            if relevant_id in result_ids:
                total_found += 1
    
    return total_found / total_relevant if total_relevant > 0 else 0.0
```

**retriever_precision@5**
- **Définition**: Of top-5 results, how many are actually relevant?
- **Calcul**: Precision@5
- **Target**: ≥ 0.80
- **Frequency**: Weekly

**retriever_ndcg@5**
- **Définition**: Normalized Discounted Cumulative Gain (ranking quality)
- **Calcul**: Standard NDCG metric
- **Target**: ≥ 0.75
- **Frequency**: Weekly

---

### 1.3 Memory Staleness

**memory_staleness**
- **Définition**: % of facts older than 30 days (potentially outdated)
- **Calcul**: 
  - Count facts with last_accessed > 30 days ago
  - Staleness = stale_facts / total_facts
- **Target**: < 20%
- **Critical**: > 30%
- **Frequency**: Daily

```python
def calc_memory_staleness(user_id: str) -> float:
    """Calculate % of stale facts (30+ days old)."""
    from datetime import datetime, timedelta
    
    cutoff = datetime.utcnow() - timedelta(days=30)
    
    all_facts = db.query(Fact).filter(
        Fact.user_id == user_id,
        Fact.status == "active"
    ).count()
    
    stale_facts = db.query(Fact).filter(
        Fact.user_id == user_id,
        Fact.status == "active",
        Fact.last_accessed_at < cutoff
    ).count()
    
    return stale_facts / all_facts if all_facts > 0 else 0.0
```

---

## 2. Métriques Chantier 2: Guardrails

### 2.1 Input Guard Metrics

**input_rejection_rate_total**
- **Définition**: % of inputs rejected by any guard
- **Calcul**: rejected_inputs / total_inputs
- **Target**: 5-10% (expect some spam/unsafe)
- **Critical**: > 20% (too aggressive)
- **Frequency**: Daily

**input_rejection_by_reason**
- pydantic_rejection_rate: Invalid format (target: < 1%)
- safety_rejection_rate: Unsafe content (target: 2-3%)
- pii_rejection_rate: High-risk PII (target: 0.5%)
- rate_limit_rejection_rate: Over quota (target: 0.5%)

**pii_detection_rate**
- **Définition**: % of inputs containing PII
- **Calcul**: inputs_with_pii / total_inputs
- **Target**: 5-15% (normal for user interactions)
- **Frequency**: Daily

---

### 2.2 Output Guard Metrics

**output_rejection_rate**
- **Définition**: % of LLM responses rejected for compliance
- **Calcul**: rejected_outputs / total_outputs
- **Target**: < 1%
- **Critical**: > 5%
- **Frequency**: Daily

**secrets_redacted_rate**
- **Définition**: % of outputs containing secrets (before redaction)
- **Calcul**: outputs_with_secrets / total_outputs
- **Target**: < 2%
- **Critical**: > 5%
- **Frequency**: Daily

**compliance_violation_rate**
- **Définition**: % of outputs violating GDPR/CNIL rules
- **Calcul**: violated_outputs / total_outputs
- **Target**: 0%
- **Frequency**: Daily

---

### 2.3 Audit Log Completeness

**audit_log_completeness**
- **Définition**: % of decisions logged correctly
- **Calcul**: 
  - Sample 100 inputs
  - Check if each has audit log entry
  - Completeness = entries_found / entries_expected
- **Target**: 100%
- **Critical**: < 99.9%
- **Frequency**: Weekly

---

## 3. Métriques Chantier 1+2+3: End-to-End

### 3.1 Latency Metrics

**llm_latency_p50 / p95 / p99**
- **Définition**: Time from user message to LLM response
- **Calcul**: LangSmith trace duration
- **Target**: p95 < 2000ms
- **Critical**: p95 > 3000ms
- **Breakdown**:
  - Retrieval: < 300ms (p95)
  - LLM call: < 1500ms (p95)
  - Output guards: < 200ms (p95)
  - Total: < 2000ms (p95)

**judge_latency_p95**
- **Target**: < 3000ms
- **Breakdown**:
  - Kimi call: < 2500ms
  - Embedding: < 1000ms
  - Persistence: < 500ms

---

### 3.2 Cost Metrics

**cost_per_turn**
- **Définition**: Total cost (Kimi + OpenAI) per user turn
- **Calcul**:
  - Input tokens × Kimi price + Output tokens × Kimi price
  - + Embedding tokens × OpenAI price
- **Target**: $0.0001-0.0005 per turn (non-judge)
- **Target**: $0.001-0.003 per turn (judge trigger)
- **Budget**: 30-turn session < $0.01

**token_efficiency**
- **Définition**: Output tokens / Input tokens
- **Target**: > 0.3 (don't waste input tokens)
- **Frequency**: Daily

```python
def calc_cost_per_turn(run: LangSmithRun) -> float:
    """Calculate total cost for a turn."""
    input_tokens = run.outputs.get("input_tokens", 0)
    output_tokens = run.outputs.get("output_tokens", 0)
    embedding_tokens = run.outputs.get("embedding_tokens", 0)
    
    # Kimi pricing: $0.3/M input, $0.6/M output
    kimi_cost = (input_tokens * 0.0000003) + (output_tokens * 0.0000006)
    
    # OpenAI embedding: $0.02/M
    embedding_cost = embedding_tokens * 0.00000002
    
    return kimi_cost + embedding_cost
```

---

### 3.3 Error Rates

**judge_error_rate**
- **Définition**: % of judge calls that fail (JSON parse error, timeout)
- **Calcul**: failed_calls / total_calls
- **Target**: < 1%
- **Critical**: > 5%
- **Frequency**: Real-time alerts

**memory_persistence_error_rate**
- **Définition**: % of facts that fail to persist
- **Target**: 0% (all-or-nothing)
- **Frequency**: Real-time alerts

**retrieval_error_rate**
- **Définition**: % of retrieval queries that fail
- **Target**: < 0.1%
- **Frequency**: Real-time alerts

---

## 4. SLA Matrix

```
Component         | Metric                    | Target   | Critical | Freq
------------------+---------------------------+----------+----------+-------
Judge             | confidence_avg            | ≥ 0.85   | < 0.80   | every 10 msgs
Judge             | hallucination_rate        | < 5%     | > 10%    | weekly
Judge             | extraction_completeness   | ≥ 0.80   | < 0.70   | monthly
Retriever         | recall@5                  | ≥ 0.80   | < 0.70   | weekly
Retriever         | precision@5               | ≥ 0.80   | < 0.70   | weekly
Memory            | staleness                 | < 20%    | > 30%    | daily
Input Guards      | rejection_rate_total      | 5-10%    | > 20%    | daily
Input Guards      | pii_detection_rate        | 5-15%    | N/A      | daily
Output Guards     | rejection_rate            | < 1%     | > 5%     | daily
Output Guards     | secrets_redacted_rate     | < 2%     | > 5%     | daily
Compliance        | audit_completeness        | 100%     | < 99.9%  | weekly
Latency           | llm_latency_p95           | < 2000ms | > 3000ms | real-time
Latency           | judge_latency_p95         | < 3000ms | > 5000ms | real-time
Cost              | cost_per_turn             | < $0.0005| < $0.001 | daily
Errors            | judge_error_rate          | < 1%     | > 5%     | real-time
Errors            | memory_persist_error_rate | 0%       | N/A      | real-time
```

---

## 5. Alerting Thresholds

### Real-Time Alerts (< 1 min response)
- Judge error rate > 5%
- Memory persistence error > 0%
- Retrieval error rate > 0.5%
- Latency p95 > 3000ms for 5 consecutive calls

### Daily Alerts (morning report)
- Judge confidence < 0.80
- Hallucination rate > 10%
- Memory staleness > 30%
- Input rejection rate > 20%
- Output rejection rate > 5%
- Cost per turn > $0.001 (non-judge)

### Weekly Alerts (Monday report)
- Recall@5 < 0.70
- Precision@5 < 0.70
- Audit completeness < 99.9%
- Token efficiency < 0.3

---

## 6. Monitoring Stack

### LangSmith Integration

```python
from langsmith import Client

client = Client()

# Get all runs from last hour
runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='createdAt > "2024-01-01T12:00:00"'
)

# Calculate metrics
judge_runs = [r for r in runs if "judge" in r.name.lower()]
judgeConfidences = [r.outputs.get("judge_confidence", 0) for r in judge_runs]
avg_confidence = sum(judgeConfidences) / len(judgeConfidences)

print(f"Judge confidence: {avg_confidence:.2f}")

# Gate deployment
if avg_confidence < 0.85:
    print("❌ Deploy BLOCKED: Judge confidence too low")
    exit(1)
else:
    print("✅ Judge quality OK, proceeding with deploy")
```

### Metrics Dashboard (Grafana / Custom)

```
Velmo 2.0 Metrics Dashboard
┌────────────────────────────────────┐
│ Judge Confidence: 0.87             │ ← Target: 0.85
├────────────────────────────────────┤
│ Hallucination Rate: 3.2%           │ ← Target: < 5%
├────────────────────────────────────┤
│ Retriever Recall@5: 0.84           │ ← Target: 0.80
├────────────────────────────────────┤
│ LLM Latency (p95): 1850ms          │ ← Target: 2000ms
├────────────────────────────────────┤
│ Cost per Turn: $0.00032            │ ← Target: < $0.0005
├────────────────────────────────────┤
│ Input Rejection Rate: 7.2%         │ ← Target: 5-10%
├────────────────────────────────────┤
│ Memory Staleness: 18%              │ ← Target: < 20%
├────────────────────────────────────┤
│ Uptime: 99.98%                     │
└────────────────────────────────────┘
```

---

## See Also

- [02_MLOPS.md](./02_MLOPS.md) — CI/CD pipeline & versioning
- [../FLOWCHARTS.md](../FLOWCHARTS.md) — Evaluation & deployment flows
- [../00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Overall architecture
