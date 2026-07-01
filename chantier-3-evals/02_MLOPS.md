# Chantier 3: MLOps & Deployment Strategy

## Vue d'Ensemble

MLOps gère le cycle de vie des modèles Velmo:

1. **Model Registry** — Track versions (Kimi, embeddings, guardrails)
2. **Version Control** — Code as git, configs in .yaml
3. **CI/CD Pipeline** — Auto-test, gate metrics, auto-deploy
4. **Data Versioning** — DVC for eval datasets
5. **Monitoring** — Health checks, auto-rollback

---

## 1. Model Registry (MLflow)

### 1.1 Models to Track

```yaml
# models.yaml
models:
  - name: kimi-2.6
    type: llm
    provider: azure-openai
    endpoint: https://eagwu-0283-resource.services.ai.azure.com/
    deployment: kimi-2.6
    api_version: 2024-08-01-preview
    versions:
      - version: 1.0
        created_at: 2024-01-01
        judge_confidence: 0.85
        judge_hallucination_rate: 0.04
        status: stable
      - version: 1.1
        created_at: 2024-01-15
        judge_confidence: 0.87
        judge_hallucination_rate: 0.03
        status: stable
  
  - name: text-embedding-3-large
    type: embedding
    provider: openai
    model_id: text-embedding-3-large
    dimensions: 3072
    versions:
      - version: 1.0
        created_at: 2024-01-01
        retriever_recall: 0.82
        status: stable
  
  - name: guardrails-rules
    type: rules
    version: 1.0
    created_at: 2024-01-01
    safety_classifier: kimi-2.6
    pii_detector: presidio
    rate_limiter: redis
    status: stable
```

### 1.2 MLflow Integration

```python
import mlflow
from datetime import datetime

mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("Velmo-2.0")

def register_model_version(
    model_name: str,
    version_tag: str,
    metrics: dict,
    params: dict,
    artifacts: dict
):
    """Register a model version in MLflow."""
    
    with mlflow.start_run(run_name=f"{model_name}_{version_tag}"):
        # Log parameters
        for key, value in params.items():
            mlflow.log_param(key, value)
        
        # Log metrics
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
        
        # Log artifacts (config files, prompts, etc.)
        for artifact_name, artifact_path in artifacts.items():
            mlflow.log_artifact(artifact_path, artifact_name)
        
        # Register model
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
        
        mv = mlflow.register_model(model_uri, model_name)
        mlflow.register_model_version(
            name=model_name,
            version=version_tag,
            run_id=mlflow.active_run().info.run_id
        )
        
        # Transition to production (if metrics pass)
        if metrics["judge_confidence"] >= 0.85:
            client = mlflow.MlflowClient()
            client.transition_model_version_stage(
                name=model_name,
                version=version_tag,
                stage="Production"
            )
```

---

## 2. Version Control & Configuration

### 2.1 Git Workflow

```bash
# Feature branch for changes
git checkout -b feature/improve-judge-extraction

# Make changes to:
# - chantier-1-memoire/: Judge prompt, extraction logic
# - chantier-2-guardrails/: Guard rules
# - chantier-3-evals/: Metrics definitions
# - .github/workflows/: CI/CD pipeline

# Commit
git add .
git commit -m "feat(chantier-1): Improve judge extraction

- Updated judge prompt for better completeness
- Added context window expansion to 15 messages
- Metrics: expected +5% recall, -2% hallucination

Testing:
- Evaluated on 100 test conversations
- Judge confidence: 0.87 (+0.02)
- Hallucination rate: 2.8% (-1.2%)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# Create PR
gh pr create --title "Improve judge extraction completeness" \
  --body "..."

# PR triggers CI pipeline automatically
```

### 2.2 Configuration Management

```yaml
# velmo-config.yaml (version controlled)
version: "1.0"
created_at: 2024-01-01

chantier_1_memory:
  window_size: 30
  max_tokens: 100000
  judge_trigger: 10  # Every 10 messages
  embedding_model: text-embedding-3-large
  min_confidence: 0.8
  
chantier_2_guardrails:
  input_validation:
    max_length: 10000
    min_length: 1
  safety_classifier: kimi-2.6
  pii_detector: presidio
  rate_limit:
    max_requests: 100
    window_seconds: 3600
  
chantier_3_evals:
  judge_confidence_target: 0.85
  judge_hallucination_target: 0.05
  retriever_recall_target: 0.80
  llm_latency_p95_target: 2000
```

### 2.3 CLAUDE.md (Architecture Changes)

```markdown
# CLAUDE.md — Velmo 2.0 Architecture

## Latest Changes

### 2024-01-15: Judge Extraction Improvement
- **What**: Expanded judge context from 10 to 15 messages
- **Why**: Increase fact completeness from 80% to 85%
- **Impact**: +0.02 confidence, -1.2% hallucination
- **Rollback**: Simple parameter change, revert if metrics degrade
- **Status**: ✅ Deployed

### 2024-01-01: Initial Deployment
- Three-layer memory architecture
- Kimi 2.6 + OpenAI embeddings
- Guardrails (Pydantic, Kimi safety, Presidio PII, Redis rate limit)
- LangSmith monitoring

---

## Architecture Overview

See [00_STACK_GLOBALE.md](./00_STACK_GLOBALE.md) for current stack.

---

## Active Experiments

None currently. Last experiment (increased window size) deployed successfully.
```

---

## 3. CI/CD Pipeline (GitHub Actions)

### 3.1 Workflow Trigger

```yaml
# .github/workflows/velmo-ci-cd.yml
name: Velmo CI/CD Pipeline

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov langsmith
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=src
      
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v
        env:
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
          AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          files: ./coverage.xml

  evaluate:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Run evaluations
        run: |
          python scripts/evaluate_metrics.py
        env:
          LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
          AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}
      
      - name: Check metrics gates
        run: |
          python scripts/check_metrics_gates.py
        env:
          LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}

  deploy:
    runs-on: ubuntu-latest
    needs: [test, evaluate]
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Build Docker image
        run: |
          docker build -t velmo:${{ github.sha }} .
          docker tag velmo:${{ github.sha }} velmo:latest
      
      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_TOKEN }} | docker login -u ${{ secrets.DOCKER_USER }} --password-stdin
          docker push velmo:${{ github.sha }}
          docker push velmo:latest
      
      - name: Deploy to staging
        run: |
          kubectl set image deployment/velmo velmo=velmo:${{ github.sha }} -n staging
          kubectl rollout status deployment/velmo -n staging
      
      - name: Monitor health (10 min)
        run: |
          python scripts/monitor_health.py --duration 600
        env:
          LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}
      
      - name: Promote to production
        if: success()
        run: |
          kubectl set image deployment/velmo velmo=velmo:${{ github.sha }} -n production
          kubectl rollout status deployment/velmo -n production
      
      - name: Notify team
        if: always()
        run: |
          python scripts/notify_slack.py --status ${{ job.status }}
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}

  rollback:
    runs-on: ubuntu-latest
    needs: deploy
    if: failure()
    
    steps:
      - name: Rollback to previous version
        run: |
          kubectl rollout undo deployment/velmo -n production
          kubectl rollout status deployment/velmo -n production
      
      - name: Create incident
        run: |
          python scripts/create_incident.py \
            --title "Deployment failed, rolled back" \
            --severity critical
        env:
          INCIDENT_WEBHOOK: ${{ secrets.INCIDENT_WEBHOOK }}
```

### 3.2 Metrics Gate Script

```python
# scripts/check_metrics_gates.py
from langsmith import Client
import sys

client = Client()

# Get runs from last evaluation
runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='createdAt >= "2024-01-01T00:00:00"',
    limit=1000
)

# Calculate metrics
judge_runs = [r for r in runs if "judge" in r.name.lower()]
judge_confidences = [
    float(r.outputs.get("judge_confidence", 0))
    for r in judge_runs
]

avg_confidence = sum(judge_confidences) / len(judge_confidences) if judge_confidences else 0

# Retriever runs
retriever_runs = [r for r in runs if "retriever" in r.name.lower()]
retrieval_scores = [
    float(r.outputs.get("retrieval_score", 0))
    for r in retriever_runs
]

avg_recall = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0

# Gate checks
GATES = {
    "judge_confidence": (avg_confidence, 0.85),
    "retriever_recall": (avg_recall, 0.80)
}

print("=" * 50)
print("Metrics Gate Check")
print("=" * 50)

all_pass = True
for gate_name, (actual, target) in GATES.items():
    status = "✅ PASS" if actual >= target else "❌ FAIL"
    print(f"{gate_name}: {actual:.2f} (target: {target:.2f}) {status}")
    if actual < target:
        all_pass = False

print("=" * 50)

if all_pass:
    print("✅ All gates passed, deployment approved")
    sys.exit(0)
else:
    print("❌ One or more gates failed, deployment blocked")
    sys.exit(1)
```

---

## 4. Blue-Green Deployment

```
Current Production (Blue)
├── Velmo:1.5
├── Judge confidence: 0.85
└── Healthy: ✅

Staging (Green)
├── Velmo:1.6
├── Judge confidence: 0.87
└── Health check: 10 min ✅

Switch Traffic:
  Blue → Green
  (instant, no downtime)

Monitor Green (30 min):
  ├─ Metrics: All OK
  ├─ Error rate: < 1%
  └─ Latency: Normal

Keep Blue as rollback for 24h:
  └─ If Green fails: instant switch back
```

---

## 5. Auto-Rollback Policy

```python
# scripts/monitor_health.py
def monitor_and_rollback(duration_seconds: int):
    """Monitor health and rollback if needed."""
    
    start_time = time.time()
    rollback_threshold = {
        "judge_confidence": 0.80,  # Critical threshold
        "error_rate": 0.05,         # 5% errors
        "latency_p95": 3000         # 3 sec latency
    }
    
    while time.time() - start_time < duration_seconds:
        metrics = get_current_metrics()
        
        # Check thresholds
        if (metrics["judge_confidence"] < rollback_threshold["judge_confidence"] or
            metrics["error_rate"] > rollback_threshold["error_rate"] or
            metrics["latency_p95"] > rollback_threshold["latency_p95"]):
            
            print("⚠️ Health check failed, triggering rollback")
            perform_rollback()
            create_incident(reason="Metrics degradation", severity="critical")
            return False
        
        time.sleep(30)  # Check every 30 sec
    
    print("✅ Health checks passed for entire duration")
    return True
```

---

## 6. Rollback Strategy

### Manual Rollback

```bash
# Immediate rollback to previous version
kubectl rollout undo deployment/velmo -n production

# Rollback to specific revision
kubectl rollout history deployment/velmo -n production
kubectl rollout undo deployment/velmo --to-revision=5 -n production
```

### Automatic Rollback

Triggered by:
1. Metrics gate failure (judge confidence < 0.80)
2. Error rate > 5% sustained for 5 min
3. Latency p95 > 3000ms sustained for 5 min
4. Manual intervention (incident response)

---

## 7. Disaster Recovery

### Backup Strategy

```bash
# Daily backups of critical data
- PostgreSQL: Full backup daily
- Pinecone indexes: Export daily as .parquet
- Config files: Git (version controlled)
- Evaluation datasets: DVC (data versioned)

# Retention: 30 days
```

### Recovery Plan

```
1. Detect outage
   └─ Automated alerts → Incident created

2. Assess impact
   ├─ Database corrupted? → Restore from backup
   ├─ Kimi endpoint down? → Use fallback (Claude)
   └─ Pinecone down? → Use PostgreSQL only (no semantic search)

3. Failover
   ├─ Primary database offline → Switch to replica
   ├─ Primary region down → Switch to secondary region
   └─ Estimated RTO: 5 minutes

4. Validate
   └─ Run health checks, verify metrics

5. Communicate
   └─ Update incident, notify users
```

---

## 8. Performance Optimization

### Continuous Optimization

```yaml
# optimization-roadmap.yaml
optimizations:
  - name: Judge context expansion
    status: completed
    gain: +5% recall, -1% hallucination
    
  - name: Retriever caching
    status: in-progress
    expected_gain: -50% latency
    
  - name: Embeddings batch processing
    status: planned
    expected_gain: -30% compute time
    
  - name: Kimi fine-tuning
    status: blocked
    reason: No API available yet
```

---

## See Also

- [01_METRICS.md](./01_METRICS.md) — Detailed metric definitions
- [../FLOWCHARTS.md](../FLOWCHARTS.md) — MLOps pipeline flow
- [../02_INTEGRATION_PLAN.md](../02_INTEGRATION_PLAN.md) — Full setup guide
