# VELMO 2.0 — Stack Technologique Globale

## Vue d'Ensemble

**Velmo 2.0** est un agent IA d'assistance avec architecture **3-chantiers** :

1. **Chantier 1 (Mémoire)** : Persistence et retrieval intelligent
2. **Chantier 2 (Guardrails)** : Validation et sécurité input/output
3. **Chantier 3 (Eval & MLOps)** : Monitoring, métriques, versioning

Toute l'orchestration via **LangChain**, avec Azure OpenAI (Kimi 2.6) comme LLM.

---

## Architecture Simplifiée

```
User Input
    │
    ├─→ [Chantier 2: Guardrails] ─→ Input validation
    │
    ├─→ [Chantier 1: Memory] ────→ Short-term + Judge + Long-term
    │
    ├─→ [LLM: Kimi 2.6 (Azure)] ─→ Response generation
    │
    ├─→ [Chantier 2: Guardrails] ─→ Output safety
    │
    └─→ [Chantier 3: Evals] ─────→ Monitoring + Metrics
```

---

## Stack Technologique Détaillé

### **Tier 1: LLM & Embedding**

| Component | Technology | Endpoint/Config | Purpose |
|-----------|-----------|-----------------|---------|
| LLM Principal | Kimi 2.6 (Azure OpenAI) | `https://eagwu-0283-resource.services.ai.azure.com/openai/v1/` | Response generation |
| Judge Agent | Kimi 2.6 (same) | same endpoint | Fact extraction (every 5 tours = 10 msgs) |
| Embedding | OpenAI text-embedding-3-large | OpenAI API | Vectorize facts for search |

### **Tier 2: Memory & Storage**

| Component | Technology | Purpose | Format |
|-----------|-----------|---------|--------|
| Short-term Window | Sliding Window Memory | 15 tours (30 messages) | In-memory FIFO |
| Facts (persistent) | PostgreSQL + pgvector | Structured fact storage | JSON + vector column |
| Vector Search | Pinecone | Semantic retrieval | Cosine similarity |
| Audit Logs | PostgreSQL audit table | GDPR compliance | Event stream |

### **Tier 3: Protection & Safety**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Input validation | Pydantic v2 | Schema enforcement |
| Content safety | Kimi 2.6 classifier | Spam/hate/violence detection |
| PII detection | Presidio | Sensitive data redaction |
| Rate limiting | Redis | Throttle by user_id |
| Compliance rules | Custom engine | GDPR/CNIL checks |

### **Tier 4: Observability**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Tracing | LangSmith | Full request tracing (auto-instrumented LangChain) |
| Metrics | LangSmith feedback + custom | Quality metrics, latency, tokens, guardrail/judge scores |
| Cost tracking | Custom dashboard | Monitor Kimi + OpenAI spend |

---

## LangChain Integration Points

```python
from langchain.chat_models import AzureChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.memory import ConversationBufferWindowMemory
from langchain.vectorstores import Pinecone
from langchain.agents import Tool, AgentExecutor, initialize_agent
from langfuse.callback import CallbackHandler as LangFuseTracer

# LLM setup (Kimi 2.6)
llm = AzureChatOpenAI(
    deployment_name="kimi-2.6",
    api_base="https://eagwu-0283-resource.services.ai.azure.com/",
    api_version="2024-08-01-preview",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0.7
)

# Embedding setup (OpenAI)
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key=os.getenv("OPENAI_API_KEY")
)

# Memory (short-term)
memory = SlidingWindowMemory(
    max_messages=30,  # 15 tours (30 messages)
    return_messages=True
)

# Vector store (Pinecone)
vectorstore = Pinecone.from_existing_index(
    index_name="velmo-facts",
    embedding=embeddings
)

# Judge agent (tools)
tools = [
    Tool(name="ExtractFacts", func=extract_facts_tool),
    Tool(name="EmbedFacts", func=embed_facts_tool),
    Tool(name="PersistFacts", func=persist_facts_tool)
]

judge_agent = initialize_agent(
    tools,
    llm,
    agent="zero-shot-react-description",
    callbacks=[LangFuseTracer(project_name="Velmo-2.0")]
)

# Main retrieval chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=vectorstore.as_retriever(),
    memory=memory,
    callbacks=[LangFuseTracer(project_name="Velmo-2.0")]
)
```

---

## Dépendances Inter-Chantiers

### **Chantier 1 → Chantier 3**
- Produces: Facts, embeddings, extraction metadata
- Consumed by: Eval metrics (judge quality, recall)

### **Chantier 2 → Chantier 1, 2, 3**
- Produces: Cleaned input, filtered output, audit logs
- Consumed by: Everyone (input/output protection)

### **Chantier 3 → CI/CD (GitHub Actions)**
- Produces: Scores LangFuse, alerts, versioning décisions
- Pipeline: test → gate (judge_confidence ≥ 0.85) → deploy
- Triggers: Auto-deploy si gate ✅, auto-rollback si dégradation

---

## Flux Complet: Turn-by-Turn

```
Turn N:
├─ Input: user_message
├─ [Chantier 2] Validate input (Pydantic)
├─ [Chantier 2] Safety check (Kimi classifier)
├─ [Chantier 1] Add to window
├─ [Chantier 1] Judge trigger? (N % 10 == 0, soit tous les 5 tours)
│  ├─ Extract facts (Kimi + tools)
│  ├─ Embed facts (OpenAI)
│  └─ Persist (PostgreSQL + Pinecone)
├─ [Chantier 1] Retriever: search similar facts
├─ [LLM] Generate response (Kimi 2.6)
├─ [Chantier 2] Output safety (Kimi classifier)
├─ [Chantier 2] PII redaction (Presidio)
├─ [Chantier 3] LangFuse trace (all above)
├─ [Chantier 3] Metrics collection
└─ Output: response to user
```

---

## Configuration Files Needed

```env
# Azure OpenAI (Kimi 2.6)
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_ENDPOINT=https://eagwu-0283-resource.services.ai.azure.com/

# OpenAI (for embeddings)
OPENAI_API_KEY=<your-key>

# Pinecone (vector DB)
PINECONE_API_KEY=<your-key>
PINECONE_ENVIRONMENT=production
PINECONE_INDEX=velmo-facts

# Redis (rate limiting)
REDIS_URL=redis://localhost:6379

# PostgreSQL (facts + audit)
DATABASE_URL=postgresql://user:pass@localhost/velmo

# LangFuse (observability)
LANGFUSE_PUBLIC_KEY=<your-public-key>
LANGFUSE_SECRET_KEY=<your-secret-key>
LANGFUSE_HOST=https://cloud.langfuse.com

# Presidio (PII detection)
PRESIDIO_ENDPOINT=http://localhost:8000  # optional, local deployment
```

---

## Coût Estimé

Per 15-tour conversation (configurable):
- Kimi LLM (9 standard turns): ~$0.00126
- Kimi Judge (1 trigger): ~$0.001
- OpenAI Embedding (3 facts): ~$0.000006
- **Total per session**: ~$0.0024
- **Per 100 users/day**: ~$0.08

*(Memory limited to 15 tours in short-term window, monitored for cost)*

---

## Prochaines Étapes

1. **01_ARCHITECTURE_OVERVIEW.md** : Diagrammes détaillés (Mermaid)
2. **02_INTEGRATION_PLAN.md** : Setup étape-par-étape
3. **Chantier 1-3 folders** : Specs complètes avec schemas
4. **CODE/** : Implementation phase

---

## Fichiers de Référence

- [Chantier 1: Mémoire](./chantier-1-memoire/README.md)
- [Chantier 2: Guardrails](./chantier-2-guardrails/README.md)
- [Chantier 3: Éval & Observabilité](./chantier-3-observabilite/README.md)
