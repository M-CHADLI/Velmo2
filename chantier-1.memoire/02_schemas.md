# Schemas — Chantier 1 : Mémoire

**Définitions formelles** des structures de données pour le Chantier 1.

---

## JSON Schema — Fait structuré

### `facts.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://velmo.local/schemas/fact.json",
  "title": "Fact (Fait persistant)",
  "description": "Structure d'un fait structuré stocké en mémoire long terme",
  "type": "object",
  "required": [
    "fact_id",
    "key",
    "value",
    "type",
    "source",
    "confidence",
    "created_at",
    "status"
  ],
  "properties": {
    "fact_id": {
      "type": "string",
      "format": "uuid",
      "description": "Identifiant unique (UUID v4)"
    },
    "key": {
      "type": "string",
      "minLength": 1,
      "maxLength": 100,
      "pattern": "^[a-z_][a-z0-9_]*$",
      "description": "Clé du fait (ex: 'contract_number')"
    },
    "value": {
      "description": "Valeur du fait (any JSON type)"
    },
    "conversation_id": {
      "type": "string",
      "description": "ID de la conversation d'où provient le fait (optionnel, si contexte local)"
    },
    "type": {
      "type": "string",
      "enum": [
        "identifier",
        "preference",
        "status",
        "context"
      ],
      "description": "Catégorie du fait"
    },
    "source": {
      "type": "string",
      "enum": [
        "user_statement",
        "extracted_from_context",
        "inferred",
        "system_default"
      ],
      "description": "Origine du fait"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Certitude du judge (0–1)"
    },
    "sensitivity": {
      "type": "string",
      "enum": [
        "low",
        "medium",
        "high"
      ],
      "default": "low",
      "description": "Niveau de sensibilité (impact sur garde-fous)"
    },
    "pii_category": {
      "type": "string",
      "enum": [
        "contract_id",
        "payment_card",
        "password",
        "email",
        "phone",
        "ssn",
        "other",
        "none"
      ],
      "default": "none",
      "description": "Catégorie PII (si applicable)"
    },
    "extracted_at_message": {
      "type": "integer",
      "minimum": 1,
      "description": "Numéro du message lors de l'extraction (traçabilité)"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp de création"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp de dernière mise à jour"
    },
    "last_accessed_at": {
      "type": "string",
      "format": "date-time",
      "description": "Timestamp du dernier accès (détection stale data)"
    },
    "version_history": {
      "type": "array",
      "maxItems": 3,
      "description": "2–3 dernières versions du fait",
      "items": {
        "type": "object",
        "required": [
          "version",
          "value",
          "timestamp"
        ],
        "properties": {
          "version": {
            "type": "integer",
            "minimum": 1,
            "description": "Numéro de version (croissant)"
          },
          "value": {
            "description": "Valeur à cette version"
          },
          "message": {
            "type": "integer",
            "description": "Numéro du message lors de cette version"
          },
          "timestamp": {
            "type": "string",
            "format": "date-time"
          },
          "reason": {
            "type": "string",
            "description": "Raison du changement (ex: 'user_update', 'correction')"
          }
        }
      }
    },
    "status": {
      "type": "string",
      "enum": [
        "active",
        "soft_deleted"
      ],
      "default": "active",
      "description": "État du fait"
    },
    "deletion_reason": {
      "type": [
        "string",
        "null"
      ],
      "description": "Raison suppression (si applicable)"
    },
    "embedding": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "description": "Vecteur d'embedding (dimension variable selon modèle)"
    }
  }
}
```

---

## JSON Schema — Métadonnées d'extraction

### `extraction_metadata.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://velmo.local/schemas/extraction_metadata.json",
  "title": "Extraction Metadata",
  "description": "Métadonnées d'un round d'extraction par le judge",
  "type": "object",
  "required": [
    "extraction_id",
    "round_number",
    "messages_analyzed",
    "created_at"
  ],
  "properties": {
    "extraction_id": {
      "type": "string",
      "format": "uuid",
      "description": "Identifiant unique du round d'extraction"
    },
    "round_number": {
      "type": "integer",
      "minimum": 1,
      "description": "Numéro du round (1, 2, 3...)"
    },
    "messages_analyzed": {
      "type": "integer",
      "minimum": 1,
      "description": "Nombre de messages traités (généralement 10)"
    },
    "judge_model": {
      "type": "string",
      "description": "Modèle LLM utilisé pour le judge (ex: 'claude-opus-4-8')"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "duration_ms": {
      "type": "integer",
      "description": "Durée d'exécution du judge (ms)"
    },
    "facts_created": {
      "type": "integer",
      "description": "Nombre de nouveaux faits créés"
    },
    "facts_updated": {
      "type": "integer",
      "description": "Nombre de faits mis à jour"
    },
    "facts_confirmed": {
      "type": "integer",
      "description": "Nombre de faits confirmés (inchangés)"
    }
  }
}
```

---

## Entity-Relationship Diagram (ERD)

### Structure base de données relationnelle

```
┌─────────────────────────────────────────┐
│      users_{user_id}_facts              │
├─────────────────────────────────────────┤
│ PK  fact_id          (UUID)             │
│     key              (String)           │
│     value            (TEXT/JSON)        │
│     conversation_id  (String)           │
│     type             (Enum)             │
│     source           (Enum)             │
│     confidence       (Float)            │
│     sensitivity      (Enum)             │
│     pii_category     (Enum)             │
│     extracted_at_msg (Int)              │
│     created_at       (DateTime)         │
│     updated_at       (DateTime)         │
│     last_accessed_at (DateTime)         │
│     version_history  (JSON Array)       │
│     status           (Enum)             │
│     deletion_reason  (Text)             │
│ FK  embedding_id     (Int)              │
└─────────────────────────────────────────┘
          │
          │ references
          ↓
┌─────────────────────────────────────────┐
│    embeddings (table centrale)          │
├─────────────────────────────────────────┤
│ PK  embedding_id     (Int)              │
│     user_id          (String)           │
│     fact_id          (UUID)             │
│     vector           (Float[])          │
│     model            (String)           │
│     created_at       (DateTime)         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ users_{user_id}_extractions_metadata    │
├─────────────────────────────────────────┤
│ PK  extraction_id    (UUID)             │
│     round_number     (Int)              │
│     messages_analyzed(Int)              │
│     judge_model      (String)           │
│     created_at       (DateTime)         │
│     facts_created    (Int)              │
│     facts_updated    (Int)              │
└─────────────────────────────────────────┘
```

---

## SQL DDL (exemple PostgreSQL)

```sql
-- Table des faits (par utilisateur)
-- À créer dynamiquement : CREATE TABLE users_{user_id}_facts (...)

CREATE TABLE users_template_facts (
  fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(100) NOT NULL,
  value JSONB,
  conversation_id VARCHAR(255),
  
  type VARCHAR(50) NOT NULL CHECK (type IN ('identifier', 'preference', 'status', 'context')),
  source VARCHAR(50) NOT NULL CHECK (source IN ('user_statement', 'extracted_from_context', 'inferred', 'system_default')),
  confidence FLOAT NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  
  sensitivity VARCHAR(50) DEFAULT 'low' CHECK (sensitivity IN ('low', 'medium', 'high')),
  pii_category VARCHAR(50) DEFAULT 'none',
  
  extracted_at_message INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_accessed_at TIMESTAMP,
  
  version_history JSONB,
  status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'soft_deleted')),
  deletion_reason TEXT,
  
  INDEX idx_key (key),
  INDEX idx_status (status),
  INDEX idx_created_at (created_at)
);

-- Table des embeddings (centrale)
CREATE TABLE embeddings (
  embedding_id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  fact_id UUID NOT NULL REFERENCES users_template_facts(fact_id),
  vector VECTOR(1536),  -- supposant modèle OpenAI ou similaire
  model VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_user_id (user_id),
  INDEX idx_fact_id (fact_id)
);

-- Métadonnées d'extraction
CREATE TABLE users_template_extractions_metadata (
  extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  round_number INTEGER NOT NULL,
  messages_analyzed INTEGER NOT NULL,
  judge_model VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  duration_ms INTEGER,
  facts_created INTEGER,
  facts_updated INTEGER,
  facts_confirmed INTEGER
);
```

---

## Vector DB Schema (exemple Pinecone)

```
Namespace: {user_id}
├─ Index name: velmo-facts
├─ Dimension: 1536 (ou selon modèle)
├─ Metric: cosine (similarité sémantique)
│
└─ Vector record:
   {
     "id": "fact_abc123",
     "values": [0.123, 0.456, ...],
     "metadata": {
       "user_id": "karim_123",
       "fact_id": "fact_abc123",
       "key": "contract_number",
       "value": "KX-9999",
       "type": "identifier",
       "status": "active",
       "sensitivity": "medium",
       "created_at": "2026-06-30T10:00:00Z"
     }
   }
```

---

## Types — Énumérations

```typescript
// Type de fait
enum FactType {
  IDENTIFIER = "identifier",      // nom, contrat, n° client
  PREFERENCE = "preference",      // langue, tutoyé, format
  STATUS = "status",              // pro/particulier, actif/suspendu
  CONTEXT = "context"             // ce qui a été demandé, problème signalé
}

// Source du fait
enum FactSource {
  USER_STATEMENT = "user_statement",           // dit explicitement
  EXTRACTED_FROM_CONTEXT = "extracted_from_context",  // déduit de la conversation
  INFERRED = "inferred",                       // logique métier
  SYSTEM_DEFAULT = "system_default"           // défaut système
}

// Sensibilité
enum Sensitivity {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high"
}

// Catégorie PII
enum PIICategory {
  CONTRACT_ID = "contract_id",
  PAYMENT_CARD = "payment_card",
  PASSWORD = "password",
  EMAIL = "email",
  PHONE = "phone",
  SSN = "ssn",
  OTHER = "other",
  NONE = "none"
}

// Statut
enum FactStatus {
  ACTIVE = "active",
  SOFT_DELETED = "soft_deleted"
}
```

---

## Validation & Constraints

**Règles de validation :**

| Contrainte | Détail |
|-----------|--------|
| `fact_id` | UUID unique, immuable |
| `key` | alphanumérique + underscore, min 1 char, max 100 chars |
| `value` | ANY (JSON compatible) |
| `confidence` | 0.0 ≤ x ≤ 1.0 |
| `type` | doit être une enum valide |
| `status` | active ou soft_deleted (jamais transitionner vers autre état) |
| `version_history` | max 3 entrées (garder les 2 plus récentes + courante) |
| `sensitivity` + `pii_category` | si `sensitivity = high`, `pii_category` requis |

---

**Version** : 1.0  
**Date** : 30 juin 2026
