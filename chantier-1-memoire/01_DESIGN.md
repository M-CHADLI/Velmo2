# Chantier 1: Design Détaillé (Mémoire)

## Vue d'Ensemble

Velmo utilise une **architecture mémoire 3 couches** pour maintenir le contexte sur 30+ tours sans perte d'information:

1. **Couche 1: Short-term** (LangChain window, 100k tokens)
2. **Couche 2: Judge** (Extraction LLM Kimi 2.6, tous 10 msgs)
3. **Couche 3: Long-term** (PostgreSQL + Pinecone, persistent)

---

## 1. Couche 1: Fenêtre Glissante (Short-term)

### 1.1 Composant: ConversationBufferWindowMemory

```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(
    k=30,                      # Keep last 30 messages
    return_messages=True,      # Return as list of Message objects
    max_token_limit=100000,    # Max tokens allowed
    human_prefix="User",       # Role names
    ai_prefix="Assistant"
)
```

### 1.2 Comportement

- **Ajout**: Chaque message utilisateur/assistant ajouté automatiquement
- **Éviction**: FIFO lorsque tokens > 100k
- **Pas de persistance**: Perte si restart de l'application
- **Accès rapide**: O(1) pour lecture/écriture

### 1.3 Budget Token

```
Calcul par message:
- Role tag: 2 tokens
- Content: ~15 tokens/phrase moyenne
- Separator: 1 token
Total: ~20 tokens par message court, ~200 tokens par long message

30 messages × ~150 tokens/msg = 4,500 tokens (baseline)
+ Context injection (retrieved facts): 2,000 tokens
+ LLM response: 2,000 tokens
= ~8,500 tokens utilisés par turn

Headroom: 100k - 8.5k = 91.5k tokens (8.5x buffer)
```

### 1.4 Trigger: Extraction Judge

**Condition**: `message_count % 10 == 0`

Après le 10e message, 20e, 30e, etc., l'agent Judge extrait les faits avant que la fenêtre ne les oublie.

---

## 2. Couche 2: Judge Agent (Fact Extraction)

### 2.1 Composant: Kimi 2.6 (Azure OpenAI)

**Rôle**: Extraire les faits structurés des 10 derniers messages.

```python
from langchain.chat_models import AzureChatOpenAI

llm = AzureChatOpenAI(
    deployment_name="kimi-2.6",
    api_base="https://eagwu-0283-resource.services.ai.azure.com/",
    api_version="2024-08-01-preview",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0.7,      # Balanced: creative but not random
    max_tokens=2048       # Room for JSON extraction
)
```

### 2.2 Judge Prompt Template

```
Role: Vous êtes un agent d'extraction de faits. Analysez la conversation et extrayez les faits clés.

Messages (derniers 10):
[Messages texte]

Extraction:
- Extrayez UNIQUEMENT les faits dont vous êtes confiant (confidence >= 0.8)
- Format: JSON structuré
- Champs obligatoires: key, value, type, confidence, source
- Pas de texte additionnel, JSON pur

Sortie JSON:
{
  "facts": [
    {
      "key": "contract_id",
      "value": "KX-4471",
      "type": "identifier",
      "confidence": 0.95,
      "source": "user_statement",
      "context": "User explicitly said contract number"
    },
    ...
  ]
}
```

### 2.3 Pipeline Judge

```
1. Trigger Check
   └─ message_count % 10 == 0?

2. Extract Facts
   ├─ Input: Last 10 messages
   ├─ Call Kimi with prompt
   └─ Output: JSON facts

3. Validate Facts
   ├─ Parse JSON
   ├─ Check schema (Pydantic)
   └─ Filter: confidence >= 0.8

4. Embed Facts
   ├─ OpenAI text-embedding-3-large
   ├─ Each fact value → 3072-dim vector
   └─ Cache embeddings

5. Persist
   ├─ PostgreSQL: INSERT facts
   ├─ Pinecone: UPSERT vectors
   └─ Audit log: Log extraction metadata

6. Success
   └─ Continue to retrieval (Couche 3)
```

### 2.4 Coût Estimation

**Par extraction (tous les 10 messages)**:

```
Judge input:
  - Prompt template: 200 tokens
  - Last 10 messages: ~1500 tokens
  - Total input: ~1700 tokens

Judge output:
  - JSON facts: ~300 tokens (5-10 facts)

OpenAI Embedding:
  - 5-10 facts × 300 tokens each = 1500 tokens

Total per extraction: ~3500 tokens
Cost: 3500 / 1M × $0.0003 = $0.00105

Per 30-turn session:
  - 3 extractions × $0.00105 = $0.00315
  - Plus 27 regular turns × 350 tokens × $0.0001 = $0.00095
  - Total: ~$0.004 per session (3x normal, but with persistent facts)
```

### 2.5 Error Handling

```python
def safe_judge_extract(messages: list[dict]) -> dict:
    """Extract facts with retry and fallback."""
    
    for attempt in range(3):
        try:
            response = llm.invoke(create_judge_prompt(messages))
            facts = json.loads(response.content)
            
            # Validate schema
            for fact in facts.get("facts", []):
                if fact["confidence"] >= 0.8:
                    yield fact
            
            return
            
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logger.warning("Judge failed 3x, skipping extraction")
                return
```

---

## 3. Couche 3: Long-term Storage

### 3.1 PostgreSQL + pgvector

**Table: facts**

```sql
CREATE TABLE facts (
    fact_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    
    -- Content
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,  -- identifier, date, quantity, etc.
    
    -- Quality
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    source VARCHAR(100),         -- user_statement, extraction, correction
    pii_category VARCHAR(100),   -- sensitive, card_number, email, etc.
    
    -- Tracking
    extracted_at_message INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    
    -- Versioning
    version INT DEFAULT 1,
    version_history JSONB,       -- [{version, value, timestamp, reason}, ...]
    
    -- GDPR
    status VARCHAR(50) DEFAULT 'active',  -- active, soft_deleted
    deletion_reason VARCHAR(255),
    
    -- Embedding
    embedding vector(3072),
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    INDEX idx_user_conversation (user_id, conversation_id),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
);
```

**Table: extraction_metadata**

```sql
CREATE TABLE extraction_metadata (
    extraction_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    round_number INT,
    
    -- Judge call
    judge_input_tokens INT,
    judge_output_tokens INT,
    judge_latency_ms INT,
    judge_confidence FLOAT,
    judge_hallucination_detected BOOLEAN DEFAULT FALSE,
    
    -- Facts produced
    facts_extracted INT,
    facts_valid INT,
    facts_invalid INT,
    
    -- Embedding
    embedding_latency_ms INT,
    
    -- Persistence
    db_latency_ms INT,
    pinecone_latency_ms INT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);
```

### 3.2 Pinecone Vector Store

**Index Configuration**:

```python
pinecone.create_index(
    name="velmo-facts",
    dimension=3072,                    # OpenAI text-embedding-3-large
    metric="cosine",
    metadata_config={"indexed": ["user_id", "conversation_id", "type"]}
)

# Namespace per user (isolation)
def upsert_facts(user_id: str, facts: list[dict]):
    vectors = []
    for fact in facts:
        vectors.append({
            "id": fact["fact_id"],
            "values": fact["embedding"],
            "metadata": {
                "user_id": user_id,
                "conversation_id": fact["conversation_id"],
                "key": fact["key"],
                "type": fact["type"],
                "confidence": fact["confidence"]
            }
        })
    
    pinecone.Index("velmo-facts").upsert(
        vectors=vectors,
        namespace=f"user_{user_id}"
    )
```

### 3.3 Retrieval (Before LLM)

```python
def retrieve_context(user_id: str, query: str, k: int = 5) -> list[dict]:
    """Retrieve top-k similar facts."""
    
    # Embed query
    query_embedding = embeddings.embed_query(query)
    
    # Search in user's namespace
    results = pinecone.Index("velmo-facts").query(
        query_embedding,
        top_k=k,
        namespace=f"user_{user_id}",
        include_metadata=True
    )
    
    # Format results
    facts = []
    for match in results.matches:
        facts.append({
            "id": match.id,
            "key": match.metadata["key"],
            "type": match.metadata["type"],
            "confidence": match.metadata["confidence"],
            "similarity": match.score
        })
    
    return facts
```

### 3.4 Version History (GDPR Compliance)

Keep 2-3 recent versions for each fact:

```python
def update_fact(fact_id: str, new_value: str, reason: str):
    """Update fact with version tracking."""
    
    fact = db.query(facts).filter(facts.fact_id == fact_id).first()
    
    # Create version entry
    old_version = {
        "version": fact.version,
        "value": fact.value,
        "timestamp": fact.updated_at,
        "reason": "previous"
    }
    
    # Append to history (keep last 3)
    history = fact.version_history or []
    history.append(old_version)
    history = history[-2:]  # Keep only last 2 old versions
    
    # Update fact
    fact.value = new_value
    fact.version += 1
    fact.version_history = history
    fact.updated_at = datetime.now()
    
    db.commit()
```

### 3.5 Soft-Delete (GDPR Right-to-Forget)

```python
def delete_fact_gdpr(fact_id: str, reason: str = "user_request"):
    """Soft-delete fact for GDPR compliance."""
    
    fact = db.query(facts).filter(facts.fact_id == fact_id).first()
    
    fact.status = "soft_deleted"
    fact.deletion_reason = reason
    fact.updated_at = datetime.now()
    
    # Log audit trail
    audit_log.create({
        "user_id": fact.user_id,
        "action": "fact_soft_delete",
        "fact_id": fact_id,
        "reason": reason,
        "timestamp": datetime.now()
    })
    
    db.commit()
    
    # Remove from Pinecone (cannot retrieve)
    pinecone.Index("velmo-facts").delete(
        ids=[fact_id],
        namespace=f"user_{fact.user_id}"
    )
```

---

## 4. Full Conversation Flow

```
Turn 1-9:
  Input → Validate → Memory.add() → Retrieve facts → LLM → Output

Turn 10 (JUDGE TRIGGER):
  Input → Validate → Memory.add()
    ↓
  Judge Extract (Kimi 2.6)
    ├─ Input: Last 10 messages
    └─ Output: JSON facts
  
  Validate facts (Pydantic, confidence >= 0.8)
  Embed facts (OpenAI)
  Persist:
    ├─ PostgreSQL INSERT
    ├─ Pinecone UPSERT
    └─ Audit log
  
  Clear old messages from window if budget > 80%
    ↓
  Retrieve facts → LLM → Output

Turn 11-19:
  Same as 1-9

Turn 20, 30, 40... (Judge triggers):
  Same as Turn 10
```

---

## 5. Isolation & Security (R3)

### Per-User Isolation

Every query includes `user_id` filter:

```python
# PostgreSQL
facts = db.query(facts) \
    .filter(facts.user_id == current_user_id) \
    .filter(facts.status == "active")

# Pinecone (namespace)
results = pinecone.query(
    vector,
    namespace=f"user_{current_user_id}"
)
```

### Audit Logging

```sql
CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    action VARCHAR(100),           -- fact_extracted, fact_retrieved, fact_deleted
    fact_id UUID,
    old_value TEXT,
    new_value TEXT,
    reason VARCHAR(255),
    timestamp TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_timestamp (user_id, timestamp)
);
```

---

## 6. Requirements Mapping

| Req | Couche | Implementation |
|-----|--------|-----------------|
| **R1**: 30+ turns | 1+2+3 | Window keeps 30 msgs, Judge extracts critical facts, DB persists |
| **R2**: Multi-session | 3 | PostgreSQL persistent storage |
| **R3**: Isolation | 1+2+3 | user_id filter on all queries, Pinecone namespaces |
| **R4**: Context budget | 1 | ConversationBufferWindowMemory(k=30, max_token_limit=100k) |
| **R5**: GDPR forget | 3 | Soft-delete status + version history, audit trail |
| **R6**: Auditability | 2+3 | Extraction metadata table + audit log table |

---

## 7. Interactions avec Autres Chantiers

**→ Chantier 2 (Guardrails)**:
- Input validé avant Memory.add()
- Facts retrieved vérifiés pour PII avant injection au LLM

**→ Chantier 3 (Evals)**:
- Extraction metadata → Analyse qualité Judge
- Retrieval scores → Metrics dashboard
- Version history → Fact staleness metrics

---

## 8. Performance Targets

| Metric | Target | SLA |
|--------|--------|-----|
| Fenêtre window add | < 10ms | < 50ms |
| Judge extract latency | < 3000ms | < 5000ms |
| Embedding latency | < 1000ms | < 2000ms |
| DB persist latency | < 500ms | < 1000ms |
| Retrieval query | < 200ms | < 500ms |
| Full turn latency | < 5000ms | < 8000ms |

---

## 9. Configuration Files

### .env

```bash
# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/velmo

# Pinecone
PINECONE_API_KEY=xxx
PINECONE_INDEX_NAME=velmo-facts

# OpenAI (Embeddings)
OPENAI_API_KEY=sk-xxx
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Azure (Kimi)
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_ENDPOINT=https://eagwu-0283-resource.services.ai.azure.com/
AZURE_OPENAI_DEPLOYMENT=kimi-2.6
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# LangSmith
LANGCHAIN_API_KEY=ls_prod_xxx
LANGCHAIN_PROJECT=Velmo-2.0
LANGCHAIN_TRACING_V2=true

# Redis (rate limiting)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
```

---

## See Also

- [02_SCHEMAS.md](./02_SCHEMAS.md) — JSON + SQL schemas détaillés
- [AZURE_KIMI_INTEGRATION.md](./AZURE_KIMI_INTEGRATION.md) — Setup Kimi 2.6
- [LANGSMITH_INTEGRATION.md](./LANGSMITH_INTEGRATION.md) — Tracing & monitoring
- [../00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Stack global
