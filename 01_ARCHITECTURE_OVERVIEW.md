# VELMO 2.0 — Vue d'Architecture Détaillée

## 1. Architecture Globale (3 Chantiers)

```mermaid
graph TB
    subgraph Input["Chantier 2: Guardrails (Input)"]
        Validator["Pydantic Validator"]
        SafetyCheck["Kimi Classifier<br/>(spam/hate/violence)"]
        PIIDetect["Presidio PII<br/>Detection"]
        RateLimit["Redis<br/>Rate Limiter"]
    end

    subgraph Memory["Chantier 1: Mémoire"]
        Window["LangChain<br/>ConversationBufferWindowMemory<br/>(100k tokens, 30 turns)"]
        Judge["Judge Agent<br/>(Kimi 2.6)<br/>Extracts every 10 msgs"]
        Embedding["OpenAI Embedding<br/>text-embedding-3-large"]
        RelDB["PostgreSQL + pgvector<br/>(facts + metadata)"]
        VecDB["Pinecone<br/>(vector search)"]
    end

    subgraph LLM["LLM Principal"]
        KimiLLM["Kimi 2.6<br/>(Azure OpenAI)<br/>Response Generation"]
    end

    subgraph Output["Chantier 2: Guardrails (Output)"]
        OutputFilter["Custom Filter<br/>(redact secrets)"]
        ComplianceCheck["Compliance Check<br/>(GDPR/CNIL)"]
    end

    subgraph Observability["Chantier 3: Evals & MLOps"]
        LangSmith["LangSmith<br/>(Tracing + Metrics)"]
        CostDash["Cost Dashboard<br/>(Token tracking)"]
    end

    User["User"]
    
    User -->|Message| Validator
    Validator --> SafetyCheck
    SafetyCheck --> PIIDetect
    PIIDetect --> RateLimit
    
    RateLimit --> Window
    Window -->|Every 10 msgs| Judge
    Judge -->|Facts| Embedding
    Embedding --> RelDB
    Embedding --> VecDB
    
    Window -->|Query| VecDB
    VecDB -->|Top-N facts| KimiLLM
    RelDB -->|Context| KimiLLM
    
    KimiLLM --> OutputFilter
    OutputFilter --> ComplianceCheck
    
    Judge -.->|Trace| LangSmith
    KimiLLM -.->|Trace| LangSmith
    Embedding -.->|Trace| LangSmith
    RelDB -.->|Trace| LangSmith
    
    LangSmith --> CostDash
    
    ComplianceCheck -->|Response| User

    style Input fill:#ffcccc
    style Memory fill:#ccffcc
    style LLM fill:#ccccff
    style Output fill:#ffcccc
    style Observability fill:#ffffcc
```

---

## 2. Sequence Diagram: Turn-by-Turn Processing

```mermaid
sequenceDiagram
    actor User
    participant Guard as Guardrails<br/>(Input)
    participant Mem as Memory<br/>(Chantier 1)
    participant Judge as Judge<br/>Agent
    participant Vec as Pinecone
    participant DB as PostgreSQL
    participant LLM as Kimi 2.6<br/>(Azure)
    participant Guard2 as Guardrails<br/>(Output)
    participant LS as LangSmith
    
    User->>Guard: Send message
    Note over Guard: Validate + Safety + PII + RateLimit
    
    Guard->>Mem: ✓ Message OK
    Mem->>Mem: Add to window
    
    alt Turn % 10 == 0
        Note over Mem,Judge: Judge Trigger!
        Mem->>Judge: Extract facts from last 10 msgs
        Judge->>Judge: Parse + structure
        Judge->>Vec: Embed 3 facts
        Vec-->>DB: Store vectors
        DB->>DB: Persist facts + metadata
        Note over DB: facts, version_history, audit_trail
    end
    
    Note over Vec: Semantic search
    Mem->>Vec: Query: "relevant facts?"
    Vec-->>LLM: Top-5 facts (similarity > 0.7)
    
    DB->>LLM: Fetch fact context
    
    LLM->>LLM: Generate response (with context)
    LLM-->>Guard2: Response
    
    Note over Guard2: Redact PII + Compliance
    Guard2->>Guard2: Filter secrets
    Guard2->>Guard2: Check GDPR rules
    
    Guard2-->>User: ✓ Safe response
    
    par Observability
        Judge->>LS: Trace execution
        LLM->>LS: Trace tokens + latency
        Vec->>LS: Trace search
        DB->>LS: Trace query
        Guard->>LS: Trace decisions
    end
```

---

## 3. Memory Layer Detail (Chantier 1)

```mermaid
graph TB
    subgraph ShortTerm["Couche 1: Court Terme"]
        Window["FIFO Window<br/>(30 messages)<br/>Budget: 100k tokens"]
    end

    subgraph Judge["Couche 2: Judge<br/>(Extraction LLM)"]
        JudgeAgent["Judge Agent<br/>(Kimi 2.6)"]
        ExtractTool["Tool: ExtractFacts<br/>→ Structured JSON"]
        EmbedTool["Tool: EmbedFacts<br/>→ OpenAI vectors"]
        PersistTool["Tool: PersistFacts<br/>→ PostgreSQL + Pinecone"]
    end

    subgraph LongTerm["Couche 3: Long Terme (Persistant)"]
        RelDB["PostgreSQL<br/>(Facts + Metadata)"]
        VecDB["Pinecone<br/>(Embeddings)"]
        Audit["PostgreSQL Audit<br/>(Deletion logs)"]
    end

    Input["Message N"]
    LLMQuery["LLM Query"]
    
    Input --> Window
    Window -->|Check: N % 10 == 0| JudgeAgent
    JudgeAgent --> ExtractTool
    ExtractTool --> EmbedTool
    EmbedTool --> PersistTool
    
    PersistTool --> RelDB
    PersistTool --> VecDB
    PersistTool --> Audit
    
    LLMQuery -.->|Semantic search| VecDB
    VecDB -.->|Top-N| LLMQuery
    RelDB -.->|Inject context| LLMQuery
    
    style ShortTerm fill:#e8f4f8
    style Judge fill:#fff4e6
    style LongTerm fill:#e8f5e9
```

---

## 4. Judge Extraction Lifecycle

```mermaid
graph LR
    Messages["Last 10 Messages<br/>(from window)"]
    Judge["Judge Agent<br/>(Kimi 2.6)"]
    Extraction["Extracted Facts<br/>{<br/>  fact_id: uuid,<br/>  key: string,<br/>  value: any,<br/>  confidence: 0-1,<br/>  type: enum,<br/>  ...<br/>}"]
    
    Embed["Embedding<br/>(OpenAI)"]
    Vectors["Dense vectors<br/>(3072-dim)"]
    
    PersistDB["PostgreSQL<br/>INSERT facts"]
    PersistVec["Pinecone<br/>UPSERT vectors"]
    
    Metadata["EXTRACTION_METADATA<br/>{<br/>  round_number,<br/>  facts_created,<br/>  judge_confidence,<br/>  duration_ms,<br/>  ...<br/>}"]
    
    Messages --> Judge
    Judge --> Extraction
    Extraction --> Embed
    Embed --> Vectors
    
    Extraction --> PersistDB
    Vectors --> PersistVec
    PersistDB --> Metadata
    
    style Judge fill:#fff4e6
    style Extraction fill:#ffebee
    style Metadata fill:#f3e5f5
```

---

## 5. Guardrails Pipeline (Chantier 2)

### Input Flow
```mermaid
graph LR
    Input["User Input"]
    Pydantic["Pydantic<br/>Validator"]
    Safety["Kimi Classifier<br/>(spam/hate/violence)"]
    PII["Presidio<br/>Scanner"]
    RateLimit["Redis<br/>Rate Limiter"]
    Audit["PostgreSQL<br/>Audit Log"]
    
    Input --> Pydantic
    Pydantic -->|✓ Valid| Safety
    Safety -->|✓ Safe| PII
    PII -->|✓ No secrets| RateLimit
    RateLimit -->|✓ Not throttled| Audit
    
    Pydantic -->|✗ Invalid| Audit
    Safety -->|✗ Unsafe| Audit
    PII -->|✗ PII found| Audit
    RateLimit -->|✗ Throttled| Audit
    
    style Input fill:#e3f2fd
    style Audit fill:#ffebee
```

### Output Flow
```mermaid
graph LR
    Response["LLM Response"]
    Redact["Custom Filter<br/>(redact secrets)"]
    Compliance["Compliance Check<br/>(GDPR/CNIL)"]
    Audit["PostgreSQL<br/>Audit Log"]
    User["User"]
    
    Response --> Redact
    Redact -->|✓ No PII| Compliance
    Compliance -->|✓ Compliant| Audit
    
    Redact -->|✗ PII found| Audit
    Compliance -->|✗ Non-compliant| Audit
    
    Audit --> User
    
    style Response fill:#e3f2fd
    style Audit fill:#ffebee
```

---

## 6. Observability: LangSmith Integration

```mermaid
graph TB
    Requests["All Requests<br/>(Judge, LLM, Embedding, Retriever)"]
    LangSmith["LangSmith<br/>(Tracing)"]
    
    Traces["Execution Traces<br/>├─ Judge call<br/>├─ Extract facts<br/>├─ Embed facts<br/>├─ LLM call<br/>├─ Retriever<br/>└─ Total latency"]
    
    Metrics["Metrics<br/>├─ Token usage<br/>├─ Judge confidence<br/>├─ Retrieval score<br/>├─ Cost<br/>└─ Latency"]
    
    Dashboard["LangSmith Dashboard<br/>├─ Project: Velmo-2.0<br/>├─ Runs: 1000+<br/>├─ Avg latency<br/>├─ Token trends<br/>└─ Error rates"]
    
    CI["CI/CD Gate<br/>if judge_confidence < 0.8:<br/>  → Block deploy"]
    
    Requests --> LangSmith
    LangSmith --> Traces
    LangSmith --> Metrics
    Metrics --> Dashboard
    Dashboard --> CI
    
    style LangSmith fill:#fff9c4
    style Dashboard fill:#fff9c4
    style CI fill:#ffcccc
```

---

## 7. Data Flow: Facts & Embeddings

```mermaid
graph LR
    Turn10["Turn #10<br/>(Judge trigger)"]
    Extract["Extract Facts<br/>(Kimi)"]
    Fact1["Fact:<br/>key=contract_id<br/>value=KX-4471<br/>confidence=0.95"]
    Fact2["Fact:<br/>key=customer_name<br/>value=Karim<br/>confidence=0.99"]
    
    Embed["Embed via OpenAI"]
    Vec1["Vector:<br/>[0.123, -0.456, ...,<br/>3072-dim]"]
    Vec2["Vector:<br/>[0.789, 0.012, ...,<br/>3072-dim]"]
    
    DBFacts["PostgreSQL<br/>FACTS TABLE<br/>id | key | value | conf | "]
    DBVecs["PostgreSQL<br/>(pgvector)"]
    Pinecone["Pinecone<br/>index: velmo-facts"]
    
    Turn10 --> Extract
    Extract --> Fact1
    Extract --> Fact2
    
    Fact1 --> Embed
    Fact2 --> Embed
    Embed --> Vec1
    Embed --> Vec2
    
    Fact1 --> DBFacts
    Fact2 --> DBFacts
    Vec1 --> DBVecs
    Vec2 --> DBVecs
    Vec1 --> Pinecone
    Vec2 --> Pinecone
    
    style Extract fill:#fff4e6
    style DBFacts fill:#e8f5e9
    style Pinecone fill:#e8f5e9
```

---

## 8. Cost Tracking (Chantier 3)

```mermaid
graph TB
    Turn["Turn N"]
    
    Kimi["Kimi 2.6<br/>Input: 234 tokens<br/>Output: 156 tokens<br/>Cost: $0.00018"]
    
    OpenAI["OpenAI Embedding<br/>Tokens: 312<br/>Cost: $0.0000062"]
    
    LangSmith["LangSmith<br/>Trace: $0.0001"]
    
    Total["Total per turn<br/>≈ $0.0002"]
    
    Dashboard["Cost Dashboard<br/>├─ Daily: $X<br/>├─ Monthly: $Y<br/>└─ Per-user avg"]
    
    Turn --> Kimi
    Turn --> OpenAI
    Turn --> LangSmith
    
    Kimi --> Total
    OpenAI --> Total
    LangSmith --> Total
    
    Total --> Dashboard
    
    style Kimi fill:#ffebee
    style OpenAI fill:#f3e5f5
    style Dashboard fill:#fff9c4
```

---

## 9. Version History & Soft-Delete (GDPR)

```mermaid
graph TB
    FactV1["Fact v1<br/>contract_id=KX-4471<br/>confidence=0.95<br/>msg #8"]
    
    FactV2["Fact v2 (updated)<br/>contract_id=KX-4472<br/>confidence=0.92<br/>msg #18"]
    
    FactV3["Fact v3 (updated)<br/>contract_id=KX-4471<br/>confidence=0.97<br/>msg #28"]
    
    VersionHistory["version_history array<br/>[<br/>  {v:1, value:KX-4471, ts, msg:8},<br/>  {v:2, value:KX-4472, ts, msg:18},<br/>  {v:3, value:KX-4471, ts, msg:28}<br/>]<br/>(keep 2-3 versions)"]
    
    SoftDelete["Right-to-be-forgotten<br/>UPDATE facts<br/>SET status='soft_deleted',<br/>    deletion_reason='GDPR request',<br/>    updated_at=now()"]
    
    AuditTrail["PostgreSQL Audit<br/>├─ who deleted<br/>├─ when<br/>├─ reason<br/>└─ recoverable"]
    
    FactV1 --> FactV2
    FactV2 --> FactV3
    FactV3 --> VersionHistory
    
    VersionHistory --> SoftDelete
    SoftDelete --> AuditTrail
    
    style VersionHistory fill:#f3e5f5
    style SoftDelete fill:#ffcccc
    style AuditTrail fill:#ffebee
```

---

## Integration Points for Code

| Layer | Code Point | LangChain Class |
|-------|-----------|-----------------|
| Input Validation | Before memory | Pydantic `BaseModel` |
| Memory Window | First step | `ConversationBufferWindowMemory` |
| Judge Trigger | Every 10 msgs | `Tool` + `AgentExecutor` |
| Embedding | Judge output | `OpenAIEmbeddings` |
| Vector Search | Before LLM | `Pinecone.as_retriever()` |
| LLM Call | Main response | `AzureChatOpenAI` |
| Output Guard | Before user | Custom function |
| Tracing | Everywhere | `LangSmithTracer` callback |

---

## Next: See Also

- [00_STACK_GLOBALE.md](./00_STACK_GLOBALE.md) — Overview + tech choices
- [02_INTEGRATION_PLAN.md](./02_INTEGRATION_PLAN.md) — Step-by-step setup
- [chantier-1-memoire/01_DESIGN.md](./chantier-1-memoire/01_DESIGN.md) — Memory design details
