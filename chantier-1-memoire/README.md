# Chantier 1: Mémoire (3-Layer Architecture)

## Objectif

Implémenter une **mémoire persistante et multilingue** pour Velmo capable de:
- Maintenir 30+ tours sans perte d'information (R1)
- Persister entre sessions (R2)
- Isoler strictement les données par utilisateur (R3)
- Gérer le budget contexte (100k tokens) (R4)
- Implémenter droit à l'oubli GDPR (R5)
- Fournir traçabilité complète (R6)

---

## Architecture: 3 Couches

```
Couche 1: Court Terme (100k tokens)
  ↓
Couche 2: Judge (Extraction LLM tous 10 msgs)
  ↓
Couche 3: Long Terme (Persistent PostgreSQL + Pinecone)
```

### Couche 1: Fenêtre Glissante (Short-term)
- LangChain `ConversationBufferWindowMemory`
- Garde les 30 derniers messages bruts
- FIFO lorsque budget dépassé
- **Pas de persistance** — peut être perdu si restart

### Couche 2: Judge Agent
- Kimi 2.6 (via Azure OpenAI)
- **Tous les 10 messages**: extrait faits structurés
- Génère embeddings (OpenAI text-embedding-3-large)
- Stocke dans PostgreSQL + Pinecone
- **Coût**: ~$0.001 par extraction

### Couche 3: Long-term Storage
- **PostgreSQL + pgvector**: Faits structurés avec métadonnées
- **Pinecone**: Embeddings pour recherche sémantique
- **Soft-delete**: GDPR compliance (pas de hard-delete)
- **Version history**: Track dernières 2-3 versions d'un fait

---

## Fichiers de Conception

| File | Purpose |
|------|---------|
| **01_DESIGN.md** | Design détaillé (6000+ lignes) + requirements mapping |
| **02_SCHEMAS.md** | JSON Schema + SQL DDL + TypeScript enums |
| **03_DIAGRAMMES.md** | 8 Mermaid diagrams (architecture, flux, lifecycle) |
| **04_DECISIONS.md** | 12 décisions critiques avec alternatives |
| **05_CAS_USAGE.md** | 7 scenarios test (R1-R6 validation) |
| **AZURE_KIMI_INTEGRATION.md** | Comment utiliser Kimi 2.6 via Azure |
| **LANGSMITH_INTEGRATION.md** | Setup tracing et monitoring LangSmith |

---

## Quick Start

### 1. Initialize Memory

```python
from langchain.memory import ConversationBufferWindowMemory
from langchain.chat_models import AzureChatOpenAI

# Short-term
memory = ConversationBufferWindowMemory(k=30, return_messages=True)

# LLM (Judge + Principal)
llm = AzureChatOpenAI(
    deployment_name="kimi-2.6",
    api_base="https://eagwu-0283-resource.services.ai.azure.com/",
    api_version="2024-08-01-preview"
)
```

### 2. Judge Extraction (Every 10 Messages)

```python
if message_count % 10 == 0:
    # Extract facts using Kimi
    result = judge_agent.run(f"Extract facts from: {last_10_messages}")
    # Result includes: fact_id, key, value, confidence, type, ...
    
    # Embed facts
    embeddings = openai_embeddings.embed_documents([fact['value']])
    
    # Persist
    db.insert_facts(facts)
    pinecone.upsert(vectors=embeddings)
```

### 3. Retrieval (Before LLM)

```python
# Query Pinecone for similar facts
similar_facts = vectorstore.similarity_search(user_message, k=5)

# Inject into LLM context
context = "\n".join([f.page_content for f in similar_facts])
response = llm.invoke(f"Context:\n{context}\n\nUser: {message}")
```

---

## Key Concepts

### Fact Schema (16 fields)

```json
{
  "fact_id": "uuid",
  "key": "contract_id",
  "value": "KX-4471",
  "conversation_id": "conv-123",
  "type": "identifier",
  "source": "user_statement",
  "confidence": 0.95,
  "sensitivity": "medium",
  "pii_category": "contract_id",
  "extracted_at_message": 8,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:00:00Z",
  "last_accessed_at": "2024-01-01T10:05:00Z",
  "version_history": [...],
  "status": "active",
  "deletion_reason": null,
  "embedding": [0.123, -0.456, ...]
}
```

### Version History (Track Changes)

Keep 2-3 most recent versions of each fact:

```json
"version_history": [
  {
    "version": 1,
    "value": "KX-4471",
    "timestamp": "2024-01-01T10:00:00Z",
    "message": 8,
    "reason": "initial"
  },
  {
    "version": 2,
    "value": "KX-4472",
    "timestamp": "2024-01-01T10:10:00Z",
    "message": 18,
    "reason": "user correction"
  }
]
```

### Soft-Delete (GDPR Right-to-Forget)

Instead of hard-delete:

```sql
UPDATE facts
SET status='soft_deleted', deletion_reason='user_request'
WHERE fact_id = 'xxx'
```

Audit trail preserved in PostgreSQL.

---

## Isolation & Security (R3)

- **Per-user isolation**: `WHERE user_id = ?` on every query
- **No cross-user retrieval**: Vectors namespaced per user
- **Audit logging**: Every access logged with user_id + timestamp

---

## Budget Management (R4)

100k tokens budget for short-term window:

```
Window size calc:
- 30 messages × ~200 tokens/msg = 6k tokens
- Buffer for context injection = 5k tokens
- LLM response = 2k tokens
- Total headroom: ~13k tokens
- Can sustain 30-turn conversations easily
```

When budget exceeded (> 80%):
→ Oldest messages drop from window
→ Judge has already extracted critical facts
→ Long-term storage remains intact

---

## Requirements Mapping

| Req | Layer | Implementation |
|-----|-------|-----------------|
| R1: 30+ turns | 1+2+3 | Short-term + Judge + Long-term persistence |
| R2: Multi-session | 3 | PostgreSQL persistent storage |
| R3: Isolation | 1+2+3 | Per-user filtering on all queries |
| R4: Context budget | 1 | ConversationBufferWindowMemory(k=30) |
| R5: GDPR forget | 3 | Soft-delete + audit trail |
| R6: Auditability | 2+3 | Extraction metadata + audit logs |

---

## Files Structure

```
chantier-1-memoire/
├── README.md                              ← You are here
├── 01_DESIGN.md                          ← Full design spec
├── 02_SCHEMAS.md                         ← JSON + SQL schemas
├── 03_DIAGRAMMES.md                      ← Mermaid diagrams
├── 04_DECISIONS.md                       ← Decision matrix
├── 05_CAS_USAGE.md                       ← Test scenarios
├── AZURE_KIMI_INTEGRATION.md             ← Kimi 2.6 setup
├── LANGSMITH_INTEGRATION.md              ← Tracing setup
└── schemas/
    ├── facts.schema.json
    └── extraction_metadata.schema.json
```

---

## Integration with Other Chantiers

**→ Chantier 2** (Guardrails):
- Input is validated before being added to memory
- Output facts are checked for PII before exposure

**→ Chantier 3** (Evals):
- Extraction metadata is analyzed for judge quality
- Fact retrieval metrics tracked via LangSmith

---

## Prochaines Étapes

1. Read [01_DESIGN.md](./01_DESIGN.md) for detailed design
2. Review [02_SCHEMAS.md](./02_SCHEMAS.md) for data structures
3. Check [03_DIAGRAMMES.md](./03_DIAGRAMMES.md) for visual flows
4. See [04_DECISIONS.md](./04_DECISIONS.md) for tradeoff analysis
5. Explore [05_CAS_USAGE.md](./05_CAS_USAGE.md) for test cases
6. Read [AZURE_KIMI_INTEGRATION.md](./AZURE_KIMI_INTEGRATION.md) for LLM setup
7. Read [LANGSMITH_INTEGRATION.md](./LANGSMITH_INTEGRATION.md) for tracing

---

## References

- [00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Overall architecture
- [01_ARCHITECTURE_OVERVIEW.md](../01_ARCHITECTURE_OVERVIEW.md) — Diagrams
- [02_INTEGRATION_PLAN.md](../02_INTEGRATION_PLAN.md) — Setup guide
- [Chantier 2: Guardrails](../chantier-2-guardrails/)
- [Chantier 3: Evals & MLOps](../chantier-3-evals/)
