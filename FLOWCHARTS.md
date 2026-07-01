# VELMO 2.0 — Flowcharts des 3 Chantiers

---

## 1. CHANTIER 1: Mémoire (3-Layer Architecture)

```mermaid
flowchart TD
    Start([User Message Arrives]) --> AddWindow["<b>Couche 1: Short-term</b><br/>Add to LangChain Window<br/>(100k tokens FIFO)"]
    
    AddWindow --> CheckCount{"Message count<br/>% 10 == 0?"}
    
    CheckCount -->|NO| Retrieve["<b>Couche 3: Retrieval</b><br/>Query Pinecone<br/>(semantic search)<br/>Get top-5 facts"]
    
    CheckCount -->|YES| Judge["<b>Couche 2: Judge</b><br/>Extract facts from<br/>last 10 messages<br/>(Kimi 2.6)"]
    
    Judge --> Validate["Validate facts<br/>(Pydantic schema)<br/>confidence >= 0.8?"]
    
    Validate -->|INVALID| SkipPersist["Skip invalid facts<br/>Log error"]
    
    Validate -->|VALID| Embed["Embed facts<br/>(OpenAI embedding)<br/>3072-dim vectors"]
    
    Embed --> Persist["<b>Persist to Storage</b><br/>- PostgreSQL: facts<br/>- Pinecone: vectors<br/>- Audit log: metadata"]
    
    Persist --> UpdateMeta["Update extraction_metadata<br/>- round_number<br/>- facts_created<br/>- judge_confidence<br/>- duration_ms"]
    
    UpdateMeta --> Retrieve
    
    SkipPersist --> Retrieve
    
    Retrieve --> BuildContext["Build LLM context<br/>- Retrieved facts<br/>- Short-term window<br/>- User message"]
    
    BuildContext --> LLMCall["<b>LLM Principal</b><br/>Kimi 2.6<br/>Generate response<br/>(with facts context)"]
    
    LLMCall --> Response["<b>OUTPUT</b><br/>Response to user<br/>(+ add to window)"]
    
    Response --> UpdateWindow["Update window<br/>with response<br/>(check budget)"]
    
    UpdateWindow --> CheckBudget{"Budget > 80%?"}
    
    CheckBudget -->|YES| Trim["Trim oldest messages<br/>from window<br/>(facts already saved)"]
    
    CheckBudget -->|NO| Trace
    
    Trim --> Trace["<b>Observability</b><br/>LangSmith trace:<br/>- Judge confidence<br/>- Retrieval score<br/>- LLM tokens<br/>- Latency"]
    
    Trace --> End([End: Response Sent])
    
    style Start fill:#e3f2fd
    style AddWindow fill:#fff4e6
    style Judge fill:#fff4e6
    style Embed fill:#fff4e6
    style Persist fill:#e8f5e9
    style Retrieve fill:#e8f5e9
    style LLMCall fill:#ccccff
    style Response fill:#c8e6c9
    style Trace fill:#fff9c4
```

---

## 2. CHANTIER 2: Guardrails (Input/Output Protection)

### 2.A — Input Flow

```mermaid
flowchart TD
    Input["<b>INPUT</b><br/>User Message"] --> Pydantic["<b>1. Validation</b><br/>Pydantic Schema<br/>- Format valid?<br/>- Length OK?<br/>- Characters allowed?"]
    
    Pydantic -->|FAIL| RejectPydantic["❌ REJECT<br/>Invalid format"]
    Pydantic -->|PASS| Safety["<b>2. Safety Check</b><br/>Kimi Classifier<br/>- Spam?<br/>- Hate speech?<br/>- Violence?"]
    
    Safety -->|FAIL| RejectSafety["❌ REJECT<br/>Unsafe content"]
    Safety -->|PASS| PII["<b>3. PII Detection</b><br/>Presidio Scanner<br/>- Payment card?<br/>- SSN?<br/>- Email/phone<br/>(contextual)?"]
    
    PII -->|FOUND| RedactPII["⚠️ Found PII<br/>Log it<br/>Continue anyway<br/>(context-aware)"]
    PII -->|NOT FOUND| RateLimit
    RedactPII --> RateLimit
    
    RateLimit["<b>4. Rate Limit</b><br/>Redis check<br/>- Max 100 req/hour?<br/>- Throttled?"]
    
    RateLimit -->|LIMIT HIT| RejectRate["❌ REJECT<br/>Rate limited"]
    RateLimit -->|OK| Audit["<b>5. Audit Log</b><br/>PostgreSQL<br/>Log: user_id, action,<br/>decision, timestamp"]
    
    Audit --> AllowInput["✅ ALLOW<br/>Message to Chantier 1"]
    
    RejectPydantic --> AuditReject["Log rejection<br/>in audit table"]
    RejectSafety --> AuditReject
    RejectRate --> AuditReject
    AuditReject --> ReturnError["Return error<br/>to user"]
    
    AllowInput --> Memory["→ Chantier 1<br/>Memory processing"]
    
    style Input fill:#e3f2fd
    style Pydantic fill:#ffcccc
    style Safety fill:#ffcccc
    style PII fill:#ffcccc
    style RateLimit fill:#ffcccc
    style Audit fill:#ffebee
    style AllowInput fill:#c8e6c9
    style Memory fill:#e8f5e9
```

### 2.B — Output Flow

```mermaid
flowchart TD
    LLMOutput["<b>LLM Response</b><br/>from Kimi 2.6"] --> Redact["<b>1. PII Redaction</b><br/>Custom filter<br/>- Redact API keys?<br/>- Redact tokens?<br/>- Redact secrets?"]
    
    Redact --> Redacted["Response with<br/>PII masked"]
    
    Redacted --> Compliance["<b>2. Compliance Check</b><br/>Custom rules<br/>- GDPR rules?<br/>- CNIL rules?<br/>- User preferences?"]
    
    Compliance -->|FAIL| RejectOutput["❌ REJECT<br/>Non-compliant"]
    Compliance -->|PASS| AuditOutput["<b>3. Audit Log</b><br/>PostgreSQL<br/>Log: user_id, action,<br/>decision, timestamp"]
    
    AuditOutput --> AllowOutput["✅ ALLOW<br/>Send to user"]
    
    RejectOutput --> AuditReject["Log rejection"]
    AuditReject --> ReturnErrorMsg["Return safe error<br/>to user<br/>'Unable to process'"]
    
    AllowOutput --> User["→ User"]
    ReturnErrorMsg --> User
    
    style LLMOutput fill:#ccccff
    style Redact fill:#ffcccc
    style Compliance fill:#ffcccc
    style AuditOutput fill:#ffebee
    style AllowOutput fill:#c8e6c9
    style User fill:#e3f2fd
```

---

## 3. CHANTIER 3: Evals & MLOps (Monitoring + Deployment)

### 3.A — Evaluation Loop

```mermaid
flowchart TD
    LangSmith["<b>LangSmith</b><br/>Capture all traces:<br/>- Judge calls<br/>- LLM calls<br/>- Retriever calls<br/>- Tool executions"]
    
    LangSmith --> CollectMetrics["<b>Collect Metrics</b><br/>Every 1000 runs:<br/>- judge_confidence_avg<br/>- judge_hallucination_rate<br/>- retriever_recall@5<br/>- llm_latency_p95<br/>- memory_staleness<br/>- audit_log_completeness"]
    
    CollectMetrics --> CompareThresholds["<b>Compare to SLA</b><br/>Check thresholds:<br/>- confidence >= 0.85?<br/>- hallucination <= 5%?<br/>- recall >= 0.8?<br/>- latency <= 2000ms?"]
    
    CompareThresholds -->|ALL PASS| HealthyMetrics["✅ HEALTHY<br/>Metrics within SLA"]
    CompareThresholds -->|ANY FAIL| DegradedMetrics["⚠️ DEGRADED<br/>Metric below SLA"]
    
    DegradedMetrics --> Alert["🚨 ALERT<br/>Send notification<br/>- Slack<br/>- Email<br/>- Dashboard"]
    
    Alert --> Investigate["Investigate cause:<br/>- Judge prompt issue?<br/>- New model worse?<br/>- Data quality problem?"]
    
    Investigate --> Rollback["Rollback to<br/>previous version?"]
    
    HealthyMetrics --> Dashboard["📊 Dashboard<br/>- Metrics trends<br/>- Cost trends<br/>- Error rates<br/>- Performance"]
    
    style LangSmith fill:#fff9c4
    style CollectMetrics fill:#fff9c4
    style CompareThresholds fill:#fff9c4
    style HealthyMetrics fill:#c8e6c9
    style DegradedMetrics fill:#ffcccc
    style Alert fill:#ffcccc
```

### 3.B — MLOps / Deployment Pipeline

```mermaid
flowchart TD
    Code["<b>Code Change</b><br/>- Judge prompt<br/>- Guardrails rule<br/>- Memory schema"]
    
    Code --> PR["Create PR<br/>on GitHub"]
    
    PR --> Trigger["<b>CI Pipeline</b><br/>(GitHub Actions)"]
    
    Trigger --> RunTests["1. Run Tests<br/>- Unit tests<br/>- Integration tests<br/>- Load tests"]
    
    RunTests -->|FAIL| FailTests["❌ FAIL<br/>Block PR"]
    FailTests --> End1([Fix & retry])
    
    RunTests -->|PASS| RunEvals["2. Run Evaluations<br/>- Load test data<br/>- Execute Chantier 1 ops<br/>- Measure metrics"]
    
    RunEvals --> CheckMetrics["3. Check Metrics Gate<br/>- judge_confidence >= 0.85?<br/>- retriever_recall >= 0.8?<br/>- No regression?"]
    
    CheckMetrics -->|FAIL| FailMetrics["❌ FAIL<br/>Block PR<br/>Metrics degraded"]
    FailMetrics --> End2([Improve & retry])
    
    CheckMetrics -->|PASS| Merge["✅ PASS<br/>Merge to main"]
    
    Merge --> BuildDeploy["<b>Build & Deploy</b><br/>- Create Docker image<br/>- Tag version<br/>- Push to registry"]
    
    BuildDeploy --> Deploy["Deploy to Prod<br/>- Update model version<br/>- Register in MLflow<br/>- Blue-green deploy"]
    
    Deploy --> Monitor["<b>Monitor</b><br/>- LangSmith traces<br/>- Metrics dashboard<br/>- Alert thresholds"]
    
    Monitor --> HealthCheck{"Metrics healthy<br/>for 1 hour?"}
    
    HealthCheck -->|YES| Success["✅ SUCCESS<br/>Deployment stable"]
    HealthCheck -->|NO| RollbackAuto["⚠️ AUTO-ROLLBACK<br/>Revert to previous<br/>version"]
    
    RollbackAuto --> Incident["📋 Incident report<br/>- What failed?<br/>- Root cause?<br/>- Fix required?"]
    
    Success --> End3([Done])
    Incident --> End4([Fix & redeploy])
    
    style Code fill:#e3f2fd
    style PR fill:#e3f2fd
    style Trigger fill:#fff9c4
    style RunTests fill:#fff9c4
    style RunEvals fill:#fff9c4
    style CheckMetrics fill:#fff9c4
    style FailTests fill:#ffcccc
    style FailMetrics fill:#ffcccc
    style Merge fill:#c8e6c9
    style Deploy fill:#c8e6c9
    style Monitor fill:#fff9c4
    style Success fill:#c8e6c9
    style RollbackAuto fill:#ffcccc
```

---

## 4. Full End-to-End Flow (All 3 Chantiers)

```mermaid
flowchart LR
    User["👤 User"]
    
    subgraph Input["CHANTIER 2: INPUT GUARDS"]
        Validate["Validate<br/>Schema"]
        Safety["Safety<br/>Check"]
        RateLimit["Rate<br/>Limit"]
    end
    
    subgraph Memory["CHANTIER 1: MEMORY"]
        Window["Short-term<br/>Window"]
        Judge["Judge Agent<br/>Extract"]
        Storage["PostgreSQL<br/>+ Pinecone"]
        Retriever["Semantic<br/>Search"]
    end
    
    subgraph LLM_Layer["LLM"]
        MainLLM["Kimi 2.6<br/>Generate<br/>Response"]
    end
    
    subgraph Output["CHANTIER 2: OUTPUT GUARDS"]
        Redact["Redact<br/>PII"]
        Compliance["Compliance<br/>Check"]
    end
    
    subgraph Observability["CHANTIER 3: EVALS & MLOPS"]
        Trace["LangSmith<br/>Traces"]
        Metrics["Metrics<br/>Collection"]
        CI["CI/CD<br/>Pipeline"]
    end
    
    User -->|Message| Validate
    Validate --> Safety
    Safety --> RateLimit
    
    RateLimit -->|Clean message| Window
    Window -->|Every 10 msgs| Judge
    Judge -->|Facts| Storage
    Storage -->|Vectors| Retriever
    
    Window -->|Query| Retriever
    Retriever -->|Top-5 facts| MainLLM
    
    MainLLM -->|Response| Redact
    Redact --> Compliance
    Compliance -->|Safe output| User
    
    Window -.->|Trace| Trace
    Judge -.->|Trace| Trace
    Retriever -.->|Trace| Trace
    MainLLM -.->|Trace| Trace
    
    Trace --> Metrics
    Metrics --> CI
    CI -.->|Deploy if metrics pass| MainLLM
    
    style User fill:#e3f2fd
    style Input fill:#ffcccc
    style Memory fill:#e8f5e9
    style LLM_Layer fill:#ccccff
    style Output fill:#ffcccc
    style Observability fill:#fff9c4
```

---

## 5. Decision Points (Chaque Étape)

```mermaid
flowchart TD
    M1["📍 Chantier 1<br/>Message Count % 10?"]
    M2["📍 Chantier 1<br/>Budget > 80%?"]
    M3["📍 Chantier 2<br/>Pydantic valid?"]
    M4["📍 Chantier 2<br/>Content safe?"]
    M5["📍 Chantier 2<br/>Rate limit OK?"]
    M6["📍 Chantier 2<br/>Output compliant?"]
    M7["📍 Chantier 3<br/>Metrics healthy?"]
    M8["📍 Chantier 3<br/>Deploy?"]
    
    M1 -->|NO| M2
    M1 -->|YES| Judge["→ Trigger Judge"]
    M2 -->|NO| Retrieve["→ Retrieve facts"]
    M2 -->|YES| Trim["→ Trim window"]
    Judge --> Store["→ Store facts"]
    Store --> Retrieve
    Trim --> Retrieve
    
    M3 -->|NO| Reject["→ Reject input"]
    M3 -->|YES| M4
    M4 -->|NO| Reject
    M4 -->|YES| M5
    M5 -->|NO| Reject
    M5 -->|YES| Process["→ Process in Chantier 1"]
    
    Process --> LLM["→ Call LLM"]
    LLM --> M6
    M6 -->|NO| RejectOut["→ Reject output"]
    M6 -->|YES| Send["→ Send to user"]
    
    Send --> M7
    RejectOut --> M7
    M7 -->|NO| M8
    M7 -->|YES| Monitor["→ Monitor"]
    M8 -->|NO| Rollback["→ Rollback"]
    M8 -->|YES| Deploy["→ Deploy"]
    
    style M1 fill:#fff4e6
    style M2 fill:#fff4e6
    style M3 fill:#ffcccc
    style M4 fill:#ffcccc
    style M5 fill:#ffcccc
    style M6 fill:#ffcccc
    style M7 fill:#fff9c4
    style M8 fill:#fff9c4
    style Reject fill:#ffebee
    style RejectOut fill:#ffebee
    style Deploy fill:#c8e6c9
    style Rollback fill:#ffcccc
```

---

## Summary Table: Decision Points

| Decision | Chantier | Condition | Action If YES | Action If NO |
|----------|----------|-----------|---------------|--------------|
| Judge trigger? | 1 | message_count % 10 == 0 | Extract facts | Skip extraction |
| Budget check? | 1 | window_tokens > 80% | Trim old messages | Continue |
| Pydantic valid? | 2 (Input) | schema match | Continue | Reject input |
| Content safe? | 2 (Input) | Kimi classifier | Continue | Reject input |
| Rate limit? | 2 (Input) | req/hour < 100 | Continue | Reject input |
| PII found? | 2 (Input) | Presidio scan | Log + Continue | Continue |
| Output compliant? | 2 (Output) | GDPR rules | Send to user | Reject output |
| Metrics healthy? | 3 | avg_confidence >= 0.85 | Deploy | Investigate |
| Auto-rollback? | 3 | degradation detected | Rollback | Stay deployed |

---

## See Also

- [00_STACK_GLOBALE.md](./00_STACK_GLOBALE.md)
- [01_ARCHITECTURE_OVERVIEW.md](./01_ARCHITECTURE_OVERVIEW.md)
- [02_INTEGRATION_PLAN.md](./02_INTEGRATION_PLAN.md)
