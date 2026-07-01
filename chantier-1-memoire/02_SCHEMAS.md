# Chantier 1: Schemas (JSON + SQL + TypeScript)

## 1. JSON Schema: Fact

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Fact",
  "description": "A single extracted fact from conversation",
  "type": "object",
  "properties": {
    "fact_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier (UUID)"
    },
    "key": {
      "type": "string",
      "minLength": 1,
      "maxLength": 255,
      "description": "Field name (contract_id, customer_name, etc.)"
    },
    "value": {
      "type": "string",
      "minLength": 1,
      "description": "Fact value"
    },
    "type": {
      "type": "string",
      "enum": ["identifier", "date", "quantity", "amount", "name", "contact", "description", "status", "other"],
      "description": "Semantic type of fact"
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Confidence score (0-1), only persist if >= 0.8"
    },
    "source": {
      "type": "string",
      "enum": ["user_statement", "extraction", "correction", "system"],
      "description": "Where the fact came from"
    },
    "pii_category": {
      "type": ["string", "null"],
      "enum": ["sensitive", "card_number", "ssn", "email", "phone", "address", "passport", null],
      "description": "PII classification (null if not PII)"
    },
    "context": {
      "type": "string",
      "description": "Why this fact was extracted"
    },
    "extracted_at_message": {
      "type": "integer",
      "minimum": 0,
      "description": "Message number when extracted"
    },
    "conversation_id": {
      "type": "string",
      "format": "uuid",
      "description": "Parent conversation"
    },
    "user_id": {
      "type": "string",
      "format": "uuid",
      "description": "Owner user"
    },
    "embedding": {
      "type": "array",
      "items": {"type": "number"},
      "minItems": 3072,
      "maxItems": 3072,
      "description": "OpenAI embedding vector (3072 dimensions)"
    }
  },
  "required": ["fact_id", "key", "value", "type", "confidence", "source", "user_id", "conversation_id"],
  "additionalProperties": false
}
```

---

## 2. JSON Schema: ExtractionMetadata

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExtractionMetadata",
  "description": "Metadata from a judge extraction round",
  "type": "object",
  "properties": {
    "extraction_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique extraction session ID"
    },
    "user_id": {
      "type": "string",
      "format": "uuid"
    },
    "conversation_id": {
      "type": "string",
      "format": "uuid"
    },
    "round_number": {
      "type": "integer",
      "minimum": 1,
      "description": "Which judge trigger (1st, 2nd, 3rd, etc.)"
    },
    "judge_input_tokens": {
      "type": "integer",
      "description": "Tokens sent to Kimi"
    },
    "judge_output_tokens": {
      "type": "integer",
      "description": "Tokens from Kimi response"
    },
    "judge_latency_ms": {
      "type": "integer",
      "description": "Time to get judge response"
    },
    "judge_confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "Average confidence of extracted facts"
    },
    "judge_hallucination_detected": {
      "type": "boolean",
      "description": "Did judge make up facts?"
    },
    "facts_extracted": {
      "type": "integer",
      "description": "Total facts returned by judge"
    },
    "facts_valid": {
      "type": "integer",
      "description": "Facts that passed validation"
    },
    "facts_invalid": {
      "type": "integer",
      "description": "Facts rejected (confidence < 0.8 or schema error)"
    },
    "embedding_latency_ms": {
      "type": "integer"
    },
    "db_latency_ms": {
      "type": "integer"
    },
    "pinecone_latency_ms": {
      "type": "integer"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    }
  },
  "required": ["extraction_id", "user_id", "conversation_id", "round_number"],
  "additionalProperties": false
}
```

---

## 3. SQL DDL

### PostgreSQL Schema

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table (referenced by facts)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);

-- Main facts table
CREATE TABLE facts (
    fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Content
    key VARCHAR(255) NOT NULL,
    value TEXT NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('identifier', 'date', 'quantity', 'amount', 'name', 'contact', 'description', 'status', 'other')),
    
    -- Quality
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source VARCHAR(100) NOT NULL CHECK (source IN ('user_statement', 'extraction', 'correction', 'system')),
    pii_category VARCHAR(100),
    context TEXT,
    
    -- Tracking
    extracted_at_message INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP,
    
    -- Versioning
    version INT DEFAULT 1 CHECK (version >= 1),
    version_history JSONB,  -- [{version: 1, value: "", timestamp: "", reason: ""}, ...]
    
    -- GDPR
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'soft_deleted')),
    deletion_reason VARCHAR(255),
    
    -- Embedding
    embedding vector(3072),
    
    -- Indexes for fast queries
    CONSTRAINT fk_user_conversation FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX idx_facts_user_conversation ON facts(user_id, conversation_id);
CREATE INDEX idx_facts_created_at ON facts(created_at);
CREATE INDEX idx_facts_status ON facts(status);
CREATE INDEX idx_facts_confidence ON facts(confidence);
CREATE INDEX idx_facts_embedding ON facts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Extraction metadata table
CREATE TABLE extraction_metadata (
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    round_number INT NOT NULL,
    
    -- Judge performance
    judge_input_tokens INT,
    judge_output_tokens INT,
    judge_latency_ms INT,
    judge_confidence FLOAT,
    judge_hallucination_detected BOOLEAN DEFAULT FALSE,
    
    -- Facts statistics
    facts_extracted INT DEFAULT 0,
    facts_valid INT DEFAULT 0,
    facts_invalid INT DEFAULT 0,
    
    -- Latency breakdown
    embedding_latency_ms INT,
    db_latency_ms INT,
    pinecone_latency_ms INT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX idx_extraction_metadata_user ON extraction_metadata(user_id);
CREATE INDEX idx_extraction_metadata_conversation ON extraction_metadata(conversation_id);
CREATE INDEX idx_extraction_metadata_created_at ON extraction_metadata(created_at);

-- Audit log table
CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,  -- fact_extracted, fact_retrieved, fact_deleted, fact_accessed
    fact_id UUID,
    old_value TEXT,
    new_value TEXT,
    reason VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_audit_user_timestamp ON audit_log(user_id, timestamp);
CREATE INDEX idx_audit_action ON audit_log(action);
```

---

## 4. TypeScript Types

```typescript
// fact.ts
export interface Fact {
  fact_id: string;           // UUID
  key: string;               // contract_id, customer_name, etc.
  value: string;             // Actual value
  type: FactType;
  confidence: number;        // 0-1
  source: FactSource;
  pii_category?: string;     // null if not PII
  context?: string;
  extracted_at_message: number;
  conversation_id: string;   // UUID
  user_id: string;           // UUID
  embedding: number[];       // 3072-dim vector
  created_at: Date;
  updated_at: Date;
  last_accessed_at?: Date;
  version: number;
  version_history?: FactVersion[];
  status: FactStatus;
  deletion_reason?: string;
}

export type FactType = 
  | "identifier"
  | "date"
  | "quantity"
  | "amount"
  | "name"
  | "contact"
  | "description"
  | "status"
  | "other";

export type FactSource = 
  | "user_statement"
  | "extraction"
  | "correction"
  | "system";

export type FactStatus = "active" | "soft_deleted";

export interface FactVersion {
  version: number;
  value: string;
  timestamp: Date;
  message_number: number;
  reason: string;
}

export interface ExtractionMetadata {
  extraction_id: string;
  user_id: string;
  conversation_id: string;
  round_number: number;
  
  judge_input_tokens: number;
  judge_output_tokens: number;
  judge_latency_ms: number;
  judge_confidence: number;
  judge_hallucination_detected: boolean;
  
  facts_extracted: number;
  facts_valid: number;
  facts_invalid: number;
  
  embedding_latency_ms: number;
  db_latency_ms: number;
  pinecone_latency_ms: number;
  
  created_at: Date;
}

export interface AuditLogEntry {
  log_id: string;
  user_id: string;
  action: "fact_extracted" | "fact_retrieved" | "fact_deleted" | "fact_accessed";
  fact_id?: string;
  old_value?: string;
  new_value?: string;
  reason?: string;
  ip_address?: string;
  user_agent?: string;
  timestamp: Date;
}
```

---

## 5. Pydantic Validation (Python)

```python
# schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class Fact(BaseModel):
    fact_id: UUID
    key: str = Field(..., min_length=1, max_length=255)
    value: str = Field(..., min_length=1)
    type: str = Field(..., regex="^(identifier|date|quantity|amount|name|contact|description|status|other)$")
    confidence: float = Field(..., ge=0, le=1)
    source: str = Field(..., regex="^(user_statement|extraction|correction|system)$")
    pii_category: Optional[str] = None
    context: Optional[str] = None
    extracted_at_message: int = Field(..., ge=0)
    conversation_id: UUID
    user_id: UUID
    embedding: Optional[List[float]] = Field(None)  # 3072 dimensions
    created_at: datetime
    updated_at: datetime
    last_accessed_at: Optional[datetime] = None
    version: int = Field(default=1, ge=1)
    version_history: Optional[List[dict]] = None
    status: str = Field(default="active", regex="^(active|soft_deleted)$")
    deletion_reason: Optional[str] = None
    
    @validator("confidence")
    def confidence_high_enough(cls, v):
        if v < 0.8:
            raise ValueError("Confidence must be >= 0.8 for persistence")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "fact_id": "550e8400-e29b-41d4-a716-446655440000",
                "key": "contract_id",
                "value": "KX-4471",
                "type": "identifier",
                "confidence": 0.95,
                "source": "user_statement",
                "extracted_at_message": 8,
                "conversation_id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "550e8400-e29b-41d4-a716-446655440002"
            }
        }

class ExtractionMetadata(BaseModel):
    extraction_id: UUID
    user_id: UUID
    conversation_id: UUID
    round_number: int = Field(..., ge=1)
    judge_input_tokens: int = Field(..., ge=0)
    judge_output_tokens: int = Field(..., ge=0)
    judge_latency_ms: int = Field(..., ge=0)
    judge_confidence: Optional[float] = Field(None, ge=0, le=1)
    judge_hallucination_detected: bool = False
    facts_extracted: int = Field(default=0, ge=0)
    facts_valid: int = Field(default=0, ge=0)
    facts_invalid: int = Field(default=0, ge=0)
    embedding_latency_ms: int = Field(default=0, ge=0)
    db_latency_ms: int = Field(default=0, ge=0)
    pinecone_latency_ms: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuditLogEntry(BaseModel):
    log_id: UUID
    user_id: UUID
    action: str = Field(..., regex="^(fact_extracted|fact_retrieved|fact_deleted|fact_accessed)$")
    fact_id: Optional[UUID] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

---

## 6. JSON Examples

### Example 1: Extracted Facts (from Judge)

```json
{
  "facts": [
    {
      "fact_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "key": "customer_name",
      "value": "Karim",
      "type": "name",
      "confidence": 0.99,
      "source": "user_statement",
      "pii_category": null,
      "context": "User explicitly introduced themselves",
      "extracted_at_message": 2,
      "conversation_id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
      "user_id": "u47ac10b-58cc-4372-a567-0e02b2c3d479"
    },
    {
      "fact_id": "f47ac10b-58cc-4372-a567-0e02b2c3d480",
      "key": "contract_id",
      "value": "KX-4471",
      "type": "identifier",
      "confidence": 0.95,
      "source": "user_statement",
      "pii_category": "contract_id",
      "context": "User mentioned contract number in turn 8",
      "extracted_at_message": 8,
      "conversation_id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
      "user_id": "u47ac10b-58cc-4372-a567-0e02b2c3d479"
    }
  ]
}
```

### Example 2: Fact with Version History

```json
{
  "fact_id": "f47ac10b-58cc-4372-a567-0e02b2c3d481",
  "key": "contract_status",
  "value": "active",
  "type": "status",
  "confidence": 0.92,
  "source": "extraction",
  "pii_category": null,
  "version": 2,
  "version_history": [
    {
      "version": 1,
      "value": "pending",
      "timestamp": "2024-01-01T10:00:00Z",
      "message_number": 5,
      "reason": "initial"
    }
  ],
  "status": "active",
  "deletion_reason": null,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:05:00Z",
  "last_accessed_at": "2024-01-01T10:10:00Z"
}
```

### Example 3: Extraction Metadata

```json
{
  "extraction_id": "e47ac10b-58cc-4372-a567-0e02b2c3d479",
  "user_id": "u47ac10b-58cc-4372-a567-0e02b2c3d479",
  "conversation_id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
  "round_number": 1,
  "judge_input_tokens": 1850,
  "judge_output_tokens": 312,
  "judge_latency_ms": 2340,
  "judge_confidence": 0.93,
  "judge_hallucination_detected": false,
  "facts_extracted": 7,
  "facts_valid": 6,
  "facts_invalid": 1,
  "embedding_latency_ms": 450,
  "db_latency_ms": 120,
  "pinecone_latency_ms": 380,
  "created_at": "2024-01-01T10:05:30Z"
}
```

---

## 7. API Request/Response

### Extract Facts Endpoint

**Request**:
```json
POST /api/v1/facts/extract
Content-Type: application/json

{
  "conversation_id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
  "messages": [
    {"role": "user", "content": "Hi, my name is Karim"},
    {"role": "assistant", "content": "Hi Karim, how can I help?"},
    ...
  ],
  "min_confidence": 0.8
}
```

**Response**:
```json
{
  "extraction_id": "e47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "success",
  "facts_extracted": 6,
  "judge_latency_ms": 2340,
  "facts": [
    {
      "fact_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "key": "customer_name",
      "value": "Karim",
      ...
    }
  ]
}
```

### Retrieve Facts Endpoint

**Request**:
```json
POST /api/v1/facts/retrieve
Content-Type: application/json

{
  "conversation_id": "c47ac10b-58cc-4372-a567-0e02b2c3d479",
  "query": "What is the customer's contract status?",
  "k": 5
}
```

**Response**:
```json
{
  "status": "success",
  "query_latency_ms": 180,
  "facts": [
    {
      "fact_id": "f47ac10b-58cc-4372-a567-0e02b2c3d481",
      "key": "contract_status",
      "value": "active",
      "similarity_score": 0.87
    }
  ]
}
```

---

## See Also

- [01_DESIGN.md](./01_DESIGN.md) — Architecture détaillée
- [AZURE_KIMI_INTEGRATION.md](./AZURE_KIMI_INTEGRATION.md) — LLM setup
- [../02_INTEGRATION_PLAN.md](../02_INTEGRATION_PLAN.md) — Full setup guide
