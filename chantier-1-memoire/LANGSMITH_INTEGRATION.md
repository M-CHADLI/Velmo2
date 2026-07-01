# LangSmith Integration for Velmo Memory

LangSmith provides **tracing, debugging, and monitoring** for all Velmo operations. It automatically captures every LangChain call (LLM, retriever, memory, tools).

---

## Setup

### 1. Account & API Key

```bash
# Create account at https://smith.langchain.com
# Generate API key in Settings
# Set environment variables

export LANGCHAIN_API_KEY="ls_prod_xxxxx"
export LANGCHAIN_PROJECT="Velmo-2.0"
export LANGCHAIN_TRACING_V2="true"
```

### 2. Load in Code

```python
import os
from langchain.callbacks import LangSmithTracer
from dotenv import load_dotenv

load_dotenv()

# Verify setup
assert os.getenv("LANGCHAIN_API_KEY"), "Missing LANGCHAIN_API_KEY"
assert os.getenv("LANGCHAIN_PROJECT"), "Missing LANGCHAIN_PROJECT"

tracer = LangSmithTracer(project_name="Velmo-2.0")
```

### 3. Add to LangChain Calls

```python
from langchain.callbacks import LangSmithTracer

# All LangChain operations automatically traced when:
# LANGCHAIN_TRACING_V2=true

# Explicit tracer (optional, for emphasis)
response = llm.invoke(
    prompt,
    config={"callbacks": [LangSmithTracer(project_name="Velmo-2.0")]}
)

# Or pass to agent
judge_agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    callbacks=[LangSmithTracer(project_name="Velmo-2.0")]
)
```

---

## What Gets Traced

LangSmith automatically captures:

### 1. LLM Calls

```
Turn #10 (Judge trigger):
├─ Input tokens: 2034 (Kimi)
├─ Output tokens: 156
├─ Total cost: $0.00018
├─ Latency: 1.2s
└─ Model: kimi-2.6 (Azure)
```

### 2. Tool Calls (Judge Agent)

```
Judge Agent Execution:
├─ Tool: ExtractFacts
│  ├─ Input: "{messages}"
│  ├─ Output: "{facts_json}"
│  └─ Duration: 1.5s
├─ Tool: EmbedFacts
│  ├─ Input: "{facts_json}"
│  ├─ Output: "{embeddings}"
│  └─ Duration: 0.3s
└─ Tool: PersistFacts
   ├─ Input: "{facts_json}"
   ├─ Output: "{result}"
   └─ Duration: 0.1s
```

### 3. Retriever Calls

```
Retriever Search:
├─ Query: "contract details"
├─ Number of results: 5
├─ Search time: 45ms
└─ Top result similarity: 0.87
```

### 4. Memory Operations

```
Memory Update:
├─ Action: add_message
├─ Role: user
├─ Content: "..."
├─ Window size (messages): 12
├─ Window size (tokens): 2400
└─ Timestamp: 2024-01-01T10:00:00Z
```

### 5. Chain Execution

```
RetrievalQA Chain:
├─ Input: "{user_message}"
├─ Retriever results: 5 documents
├─ Context tokens: 1200
├─ LLM output: "{response}"
├─ Total latency: 2.3s
└─ Tokens total: 1456
```

---

## Accessing Traces

### Via Dashboard

1. Go to https://smith.langchain.com
2. Select project "Velmo-2.0"
3. Browse "Runs" tab
4. Click on any run to see full trace

### Programmatically

```python
from langsmith import Client

client = Client()

# Get recent runs
runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='startTime > "2024-01-01"',
    limit=100
)

# Analyze
for run in runs:
    print(f"Run: {run.id}")
    print(f"  Duration: {(run.end_time - run.start_time).total_seconds()}s")
    print(f"  Status: {run.status}")
    print(f"  Inputs: {run.inputs}")
    print(f"  Outputs: {run.outputs}")
```

---

## Monitoring Key Metrics (Chantier 1)

### Judge Quality Metrics

```python
from langsmith import Client

client = Client()

# Filter judge runs
judge_runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='name="Judge Agent"'
)

# Analyze confidence
confidences = []
for run in judge_runs:
    output = run.outputs.get("output", "{}")
    facts = json.loads(output).get("facts", [])
    confidences.extend([f.get("confidence", 0) for f in facts])

avg_confidence = sum(confidences) / len(confidences) if confidences else 0
print(f"Judge avg confidence: {avg_confidence:.2f}")

# CI Gate
if avg_confidence < 0.85:
    print("❌ Judge quality degraded, BLOCK deployment")
    exit(1)
```

### Retriever Quality Metrics

```python
# Filter retriever runs
retriever_runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='name="Pinecone Retriever"'
)

# Analyze relevance scores
relevance_scores = []
for run in retriever_runs:
    docs = run.outputs.get("output", [])
    for doc in docs:
        score = doc.metadata.get("_score", 0)
        relevance_scores.append(score)

avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
print(f"Retriever avg relevance: {avg_relevance:.2f}")
```

### Latency Metrics

```python
# Calculate latencies
latencies = []
for run in judge_runs:
    duration_sec = (run.end_time - run.start_time).total_seconds()
    latencies.append(duration_sec)

avg_latency = sum(latencies) / len(latencies)
p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

print(f"Judge avg latency: {avg_latency:.2f}s")
print(f"Judge p95 latency: {p95_latency:.2f}s")

# SLA: < 3s per judge execution
if p95_latency > 3.0:
    print("⚠️ Judge latency SLA violated")
```

### Token Usage & Cost

```python
# Sum tokens per model
kimi_tokens = 0
openai_tokens = 0

for run in judge_runs:
    # LangSmith provides token estimates
    # Actual token count in run.metadata
    metadata = run.metadata or {}
    if "tokens" in metadata:
        if run.extra.get("model") == "kimi-2.6":
            kimi_tokens += metadata["tokens"]
        elif "embedding" in run.name:
            openai_tokens += metadata["tokens"]

print(f"Kimi tokens (1k runs): {kimi_tokens}")
print(f"OpenAI tokens (1k runs): {openai_tokens}")

# Cost estimate
kimi_cost = (kimi_tokens / 1e6) * 0.0003  # $0.3/M tokens
openai_cost = (openai_tokens / 1e6) * 0.00002  # $0.02/M tokens

print(f"Estimated cost: ${kimi_cost + openai_cost:.4f}")
```

---

## Custom Annotations (Feedback Loop)

Mark runs as correct/incorrect for learning:

```python
client = Client()

# Get a specific run
run = client.read_run(run_id="xxx")

# Provide feedback
client.create_feedback(
    run_id=run.id,
    key="judge_correctness",
    score=1.0,  # 1.0 = correct, 0.0 = incorrect
    feedback_source_type="manual",
    comment="All facts extracted correctly"
)

# Later, query feedback for analysis
feedbacks = client.list_feedback(
    run_ids=[run.id],
    key="judge_correctness"
)

accuracy = sum(f.score for f in feedbacks) / len(feedbacks)
print(f"Judge accuracy (manual feedback): {accuracy:.2%}")
```

---

## Debugging with LangSmith

### Example: Judge Extraction Issue

**Scenario**: Judge only extracted 1 fact instead of 3. Why?

**Steps**:

1. Go to LangSmith dashboard
2. Find the judge run (Turn #10)
3. Click on "ExtractFacts" tool call
4. Inspect:
   - **Input**: The prompt sent to Kimi
   - **Output**: The JSON response
   - **Tokens**: How many tokens Kimi used
   - **Duration**: How long it took

5. **Analysis**:
   ```
   Input prompt: "Extract facts from: [10 messages]..."
   
   Output: {"facts": [{"key": "name", "value": "Karim", ...}]}
   
   Issue: Judge prompt may be too vague
   → Judge only extracted obvious fact (name)
   → Missed contract_id and type
   
   Fix: Add explicit instruction
   "Extract: name, contract_id, service_type, etc."
   ```

6. **Re-test**: Run with improved prompt, verify in LangSmith

---

## Alerts & Monitoring

### Set up CI/CD Gates

```yaml
# .github/workflows/verify-judge.yml
name: Verify Judge Quality

on: pull_request

jobs:
  check-judge:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Check Judge Metrics
        run: |
          python scripts/check_judge_metrics.py
          # Exits with status 1 if metrics below threshold
```

### Python Script for CI Gate

```python
# scripts/check_judge_metrics.py
from langsmith import Client
import sys

client = Client()

runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='createdAt >= "2024-01-01"',
    limit=1000
)

# Calculate metrics
confidences = []
latencies = []

for run in runs:
    if "judge" in run.name.lower():
        confidences.append(run.outputs.get("confidence", 0))
        latencies.append((run.end_time - run.start_time).total_seconds())

avg_confidence = sum(confidences) / len(confidences) if confidences else 0
avg_latency = sum(latencies) / len(latencies) if latencies else 0

print(f"Judge Metrics:")
print(f"  Confidence: {avg_confidence:.2f} (target: > 0.85)")
print(f"  Latency: {avg_latency:.2f}s (target: < 3s)")

# Gates
if avg_confidence < 0.85:
    print("❌ FAILED: Judge confidence below threshold")
    sys.exit(1)

if avg_latency > 3.0:
    print("❌ FAILED: Judge latency exceeds SLA")
    sys.exit(1)

print("✅ PASSED: All metrics healthy")
```

---

## Exporting Data for Analysis

### Export Runs as CSV

```python
import csv
from langsmith import Client

client = Client()

runs = client.list_runs(
    project_name="Velmo-2.0",
    limit=1000
)

# Write to CSV
with open("velmo_runs.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "run_id", "name", "status", "duration_s", "tokens", "model"
    ])
    writer.writeheader()
    
    for run in runs:
        duration = (run.end_time - run.start_time).total_seconds()
        writer.writerow({
            "run_id": run.id,
            "name": run.name,
            "status": run.status,
            "duration_s": duration,
            "tokens": run.outputs.get("tokens", 0),
            "model": run.extra.get("model", "unknown")
        })

print("Exported to velmo_runs.csv")
```

### Generate Reports

```python
from langsmith import Client
import json

client = Client()

# Daily report
runs = client.list_runs(
    project_name="Velmo-2.0",
    filter='createdAt >= "2024-01-01" AND createdAt < "2024-01-02"'
)

report = {
    "date": "2024-01-01",
    "total_runs": len(runs),
    "judge_runs": sum(1 for r in runs if "judge" in r.name.lower()),
    "retriever_runs": sum(1 for r in runs if "retriever" in r.name.lower()),
    "avg_latency_s": sum(
        (r.end_time - r.start_time).total_seconds() for r in runs
    ) / len(runs),
    "success_rate": sum(1 for r in runs if r.status == "success") / len(runs)
}

with open("report_2024_01_01.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Report: {report['total_runs']} runs, {report['success_rate']:.1%} success")
```

---

## Troubleshooting LangSmith

| Issue | Cause | Solution |
|-------|-------|----------|
| No traces appearing | LANGCHAIN_TRACING_V2 not set | Set `export LANGCHAIN_TRACING_V2=true` |
| 401 Unauthorized | Invalid API key | Check `LANGCHAIN_API_KEY` in .env |
| Project not found | Project name mismatch | Verify `LANGCHAIN_PROJECT="Velmo-2.0"` exactly |
| Slow dashboard | Too many runs | Use time filters in queries |
| High costs | Tracing overhead | LangSmith tracing is cheap (~$0.0001/trace) |

---

## Best Practices

1. **Use explicit run names**:
   ```python
   # Good: Clear what's being traced
   llm.invoke(prompt, config={"run_name": "judge_extract_facts"})
   
   # Bad: Generic
   llm.invoke(prompt)
   ```

2. **Add custom metadata**:
   ```python
   llm.invoke(
       prompt,
       config={
           "metadata": {
               "user_id": "karim-123",
               "turn_number": 10,
               "judge_trigger": True
           }
       }
   )
   ```

3. **Monitor regularly**:
   - Daily: Check judge confidence trend
   - Weekly: Review cost trends
   - Monthly: Analyze quality metrics

4. **Archive old runs**:
   - Keep 3 months of detailed traces
   - Archive older runs for compliance

---

## See Also

- [AZURE_KIMI_INTEGRATION.md](./AZURE_KIMI_INTEGRATION.md) — LLM setup
- [../00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Overall stack
- [../chantier-3-evals/](../chantier-3-evals/) — Evaluation metrics
