# Chantier 1: Architecture Mémoire (PostgreSQL JSONB + pgvector)

## 1. Contraintes & Exigences

| ID | Exigence (brief) | Description | Implication technique |
|----|------------------|-------------|----------------------|
| **R1** | Fil ≥ 30 tours | Tenir une conversation d'au moins 30 tours sans perdre une info donnée au tout début | Short-term sliding window + récupération depuis long-term |
| **R2** | Persistance multi-session | Se souvenir, d'une session à l'autre, des faits et préférences durables d'un même utilisateur | Long-term storage durable (PostgreSQL) |
| **R3** | Isolation stricte | La mémoire d'un utilisateur n'est jamais accessible à un autre | Filter `WHERE user_id = ?` partout |
| **R4** | Tenir la fenêtre de contexte | Au-delà du budget de tokens, résumer / sélectionner sans perdre l'info critique | Résumé glissant + recherche sémantique (pas de troncature aveugle) |
| **R5** | Droit à l'oubli (RGPD) | Un utilisateur peut demander d'oublier une info, avec suppression effective et vérifiable | Suppression tracée (`status`, `deletion_reason`) + preuve |
| **R6** | Traçabilité | Pouvoir inspecter ce que l'agent a retenu d'un utilisateur | Endpoint d'inspection + audit log, timestamp everywhere |

---

## 2. Flux de Données (End-to-End)

```
┌────────────────────────────────────────────────────────────────────┐
│                     USER MESSAGE ARRIVES                            │
│                   "Mon contrat est KX-4471"                         │
└────────────────┬─────────────────────────────────────────────────┘
                 │
                 ↓
        ┌────────────────────┐
        │ VALIDATION         │
        │ (Chantier 2)       │
        │ - Pydantic schema  │
        │ - Safety check     │
        │ - PII detection    │
        └────────┬───────────┘
                 │ ✅ Valid
                 ↓
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  LAYER 1: SHORT-TERM (RAM)   ┃
    ┃  Sliding Window Memory        ┃
    ┗━━━━━━━━━┬━━━━━━━━━━━━━━━━━━┛
              │
              ├─ Add message to window
              ├─ Keep last 30 messages (15 tours)
              │
              ├─ Retrieve context from DB
              │  (semantic search on embeddings)
              │
              └─→ LLM generates response
                  "D'accord, contrat KX-4471 noté!"
                  
                  ↓
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  EVERY 5 TOURS (10 messages):             ┃
    ┃  TRIGGER JUDGE EXTRACTION                 ┃
    ┗━━━━━━━━━┬━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
              │
              ├─ Last 10 messages → LLM (Judge)
              │  "Extract facts from conversation"
              │
              ├─ Judge outputs JSON:
              │  {
              │    "facts": [
              │      {
              │        "key": "contract_id",
              │        "value": "KX-4471",
              │        "type": "identifier",
              │        "confidence": 0.95
              │      }
              │    ]
              │  }
              │
              ├─ Generate embedding
              │  text-embedding-3-small → [0.234, 0.891, ...]
              │
              └─→ PERSIST TO POSTGRESQL
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃  LAYER 3: LONG-TERM (PostgreSQL)          ┃
    ┃  JSONB + pgvector (All-in-One)            ┃
    ┗━━━━━━━━━┬━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
              │
              ├─ INSERT INTO facts
              │  {
              │    fact_id: uuid,
              │    user_id: user_xyz,
              │    conversation_id: conv_123,
              │    data: {                      ← JSONB flexible
              │      key: "contract_id",
              │      value: "KX-4471",
              │      type: "identifier",
              │      confidence: 0.95,
              │      source: "user_statement"
              │    },
              │    embedding: [0.234, 0.891, ...]  ← pgvector
              │    created_at: NOW(),
              │    status: 'active'
              │  }
              │
              ├─ Index on embedding (HNSW)
              │  for fast semantic search
              │
              └─ Audit log entry
                 "fact_extracted", timestamp, user_id
```

---

## 3. Architecture: PostgreSQL All-in-One

### Why PostgreSQL JSONB + pgvector?

| Aspekt | Relational DB | NoSQL | **PostgreSQL JSONB+pgvector** |
|--------|---------------|-------|------|
| Flexibilité | ❌ Schéma fixe | ✅ JSON libre | ✅ JSONB = flexible |
| Vecteurs | ❌ Besoin store séparé | ⚠️ Limité | ✅ pgvector natif |
| ACID | ✅ Fort | ❌ Eventual | ✅ Fort |
| Transactions | ✅ Atomiques | ❌ Loose | ✅ Atomiques (fact+embedding ensemble) |
| GDPR Compliance | ✅ Facile | ⚠️ Complexe | ✅ Facile |
| Audit Trail | ✅ Natif | ⚠️ Manual | ✅ Natif |
| Coût | $$ | $$ | $ (one store only) |
| Maintenance | Simple | Simple | **Simpler** |

### Key Features

**JSONB**: Store anything without schema migrations
```json
{
  "key": "contract_id",
  "value": "KX-4471",
  "type": "identifier",
  "confidence": 0.95,
  "source": "user_statement",
  "custom_field_1": "anything",
  "custom_field_2": {...}
}
```

**pgvector**: Native semantic search
```sql
SELECT * FROM facts
WHERE user_id = 'user_xyz'
ORDER BY embedding <-> query_embedding  -- Cosine similarity
LIMIT 5;
```

**Indices**: HNSW for speed
```sql
CREATE INDEX ON facts USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

---

## 4. Database Schema

### Table: facts

```sql
CREATE TABLE facts (
    -- Identity
    fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    
    -- Flexible content (JSONB)
    data JSONB NOT NULL,
    -- Contains: key, value, type, confidence, source, context, etc.
    -- Can evolve without migrations!
    
    -- Embedding for semantic search (pgvector)
    embedding vector(384),              -- Dimension depends on model
    
    -- Metadata
    extracted_at_message INT,           -- Which message triggered extraction
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_accessed_at TIMESTAMP,
    
    -- GDPR Compliance
    status VARCHAR(20) DEFAULT 'active',  -- active, soft_deleted
    deletion_reason VARCHAR(255),
    
    -- Versioning
    version INT DEFAULT 1,
    version_history JSONB,              -- [{version, value, timestamp, reason}, ...]
    
    -- Constraints & Indexes
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- Indices
CREATE INDEX idx_facts_user_id ON facts(user_id);
CREATE INDEX idx_facts_conversation_id ON facts(conversation_id);
CREATE INDEX idx_facts_created_at ON facts(created_at);
CREATE INDEX idx_facts_status ON facts(status);

-- Vector index for semantic search (FAST!)
CREATE INDEX idx_facts_embedding ON facts USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- JSONB index for flexible queries
CREATE INDEX idx_facts_data ON facts USING GIN (data);
```

### Table: extraction_metadata

```sql
CREATE TABLE extraction_metadata (
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    conversation_id UUID NOT NULL,
    
    -- Extraction details
    round_number INT,
    messages_count INT,
    
    -- Judge quality
    judge_confidence FLOAT,
    judge_latency_ms INT,
    
    -- Facts produced
    facts_extracted INT,
    facts_valid INT,
    
    -- Embeddings
    embedding_latency_ms INT,
    embedding_model VARCHAR(100),
    embedding_dimensions INT,
    
    -- Persistence
    db_latency_ms INT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX idx_extraction_metadata_user_id ON extraction_metadata(user_id);
CREATE INDEX idx_extraction_metadata_created_at ON extraction_metadata(created_at);
```

### Table: audit_log

```sql
CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Action details
    action VARCHAR(100),                -- fact_extracted, fact_accessed, fact_deleted
    fact_id UUID,
    old_value JSONB,
    new_value JSONB,
    
    -- Context
    reason VARCHAR(255),
    ip_address INET,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
```

---

## 5. Code Examples

### 5.1 Extraction & Persistence

```python
from datetime import datetime
import json

def extract_and_persist_facts(
    user_id: str,
    conversation_id: str,
    messages: list[dict],
    llm,
    embedding_model
):
    """Extract facts every 5 tours and persist to PostgreSQL."""
    
    # Step 1: Judge extraction
    judge_prompt = f"Extract facts from: {messages}"
    judge_response = llm.invoke(judge_prompt)
    facts_json = json.loads(judge_response)
    
    # Step 2: Validate
    valid_facts = [
        f for f in facts_json.get("facts", [])
        if f.get("confidence", 0) >= 0.8
    ]
    
    # Step 3: Embed each fact
    embeddings = []
    for fact in valid_facts:
        embedding = embedding_model.embed(fact["value"])
        embeddings.append(embedding)
    
    # Step 4: Persist to PostgreSQL (JSONB + pgvector in one transaction)
    with db.transaction():
        for fact, embedding in zip(valid_facts, embeddings):
            db.execute("""
                INSERT INTO facts (
                    user_id, conversation_id, data, embedding,
                    extracted_at_message, created_at, status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, 'active'
                )
            """, (
                user_id,
                conversation_id,
                json.dumps(fact),           # Store fact as JSONB
                embedding,                   # pgvector column
                len(messages),
                datetime.now()
            ))
            
            # Audit log
            db.execute("""
                INSERT INTO audit_log (user_id, action, fact_id, reason)
                VALUES (%s, 'fact_extracted', %s, 'judge_trigger')
            """, (user_id, fact["id"]))
```

### 5.2 Retrieval (Semantic Search)

```python
def retrieve_context(
    user_id: str,
    query: str,
    embedding_model,
    k: int = 5
):
    """Retrieve top-k similar facts using vector similarity."""
    
    # Embed query
    query_embedding = embedding_model.embed(query)
    
    # Semantic search in PostgreSQL
    results = db.query("""
        SELECT 
            fact_id,
            user_id,
            data,
            embedding <-> %s AS distance,
            1 - (embedding <=> %s) AS similarity
        FROM facts
        WHERE user_id = %s
          AND status = 'active'
        ORDER BY embedding <-> %s
        LIMIT %s
    """, (query_embedding, query_embedding, user_id, query_embedding, k))
    
    # Return facts with similarity scores
    facts = []
    for row in results:
        fact = json.loads(row['data'])
        fact['similarity'] = row['similarity']
        fact['fact_id'] = row['fact_id']
        facts.append(fact)
    
    return facts
```

### 5.3 GDPR Soft-Delete

```python
def delete_fact_gdpr(fact_id: str, user_id: str, reason: str):
    """Soft-delete a fact for GDPR compliance."""
    
    with db.transaction():
        # Soft-delete
        db.execute("""
            UPDATE facts
            SET status = 'soft_deleted',
                deletion_reason = %s,
                updated_at = NOW()
            WHERE fact_id = %s AND user_id = %s
        """, (reason, fact_id, user_id))
        
        # Audit trail
        db.execute("""
            INSERT INTO audit_log (
                user_id, action, fact_id, reason
            ) VALUES (%s, 'fact_soft_delete', %s, %s)
        """, (user_id, fact_id, reason))
```

### 5.4 Version History (Track Changes)

```python
def update_fact_value(fact_id: str, new_value: str, reason: str):
    """Update fact and keep version history."""
    
    # Get old fact
    old_fact = db.query_one("""
        SELECT data, version, version_history
        FROM facts
        WHERE fact_id = %s
    """, (fact_id,))
    
    # Build version history
    version_entry = {
        "version": old_fact['version'],
        "value": old_fact['data']['value'],
        "timestamp": datetime.now().isoformat(),
        "reason": reason
    }
    
    history = old_fact['version_history'] or []
    history.append(version_entry)
    
    # Keep only last 3 versions
    history = history[-3:]
    
    # Update fact
    db.execute("""
        UPDATE facts
        SET data = jsonb_set(data, '{value}', to_jsonb(%s)),
            version = version + 1,
            version_history = %s,
            updated_at = NOW()
        WHERE fact_id = %s
    """, (new_value, json.dumps(history), fact_id))
```

---

## 6. Configuration

```yaml
# config.yaml
database:
  type: postgresql
  connection_string: "postgresql://user:pass@localhost:5432/velmo"
  
memory:
  short_term:
    max_messages: 30              # 15 tours
    max_size_bytes: 524288        # 512 KB
    eviction_policy: lru
  
  extraction:
    trigger_frequency: 5          # Every 5 tours
    trigger_message_count: 10     # Every 10 messages
    confidence_threshold: 0.8
  
embeddings:
  model: "text-embedding-3-small"
  dimensions: 384
  cache_enabled: true

pgvector:
  index_type: hnsw                # or ivfflat
  metric: cosine                  # or l2, inner_product
  m: 16                           # HNSW parameter
  ef_construction: 64             # HNSW parameter
```

---

## 7. Migration & Setup

```bash
# 1. Install pgvector extension
psql -d velmo -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 2. Run migrations
psql -d velmo -f schema.sql

# 3. Create indices
psql -d velmo -f indices.sql

# 4. Verify
psql -d velmo -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

---

## 8. Performance Targets

| Operation | Target | Status |
|-----------|--------|--------|
| Add to short-term window | < 5ms | ✅ RAM |
| Judge extraction | < 3000ms | ⏱️ LLM dependent |
| Embedding generation | < 1000ms | ⏱️ Model dependent |
| Semantic search (k=5) | < 50ms | ✅ pgvector HNSW |
| DB insert | < 10ms | ✅ PostgreSQL |
| GDPR soft-delete | < 20ms | ✅ Single UPDATE |

---

## See Also

- [02_SCHEMAS.md](./02_SCHEMAS.md) — JSON Schema examples
- [../00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Full stack overview
