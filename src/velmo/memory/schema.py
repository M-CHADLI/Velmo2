from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class FactData(BaseModel):
    """Structured fact details stored inside the JSONB 'data' column."""
    key: str = Field(..., description="The unique type/key of the fact (e.g. contract_id, preference, username)")
    value: str = Field(..., description="The value of the fact")
    type: str = Field("preference", description="Category of fact (e.g. identifier, preference, user_fact)")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score assigned by the Judge")
    source: str = Field("user_statement", description="How the fact was gathered (e.g. user_statement, context_inference)")
    context: Optional[str] = Field(None, description="The message context from which this fact was extracted")

class Fact(BaseModel):
    """Full Fact database record representation."""
    fact_id: Optional[str] = None
    user_id: str
    conversation_id: str
    data: FactData
    embedding: Optional[list[float]] = None
    extracted_at_message: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    status: str = "active"
    deletion_reason: Optional[str] = None
    version: int = 1
    version_history: list[dict[str, Any]] = Field(default_factory=list)

class ExtractionMetadata(BaseModel):
    """Metadata regarding a Judge fact extraction operation."""
    extraction_id: Optional[str] = None
    user_id: str
    conversation_id: str
    round_number: Optional[int] = None
    messages_count: Optional[int] = None
    judge_confidence: Optional[float] = None
    judge_latency_ms: Optional[int] = None
    facts_extracted: Optional[int] = None
    facts_valid: Optional[int] = None
    embedding_latency_ms: Optional[int] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    db_latency_ms: Optional[int] = None
    created_at: Optional[datetime] = None

class AuditLog(BaseModel):
    """Audit log entry for database state tracking (GDPR/Traceability compliance)."""
    log_id: Optional[str] = None
    user_id: str
    action: str  # fact_extracted, fact_accessed, fact_deleted, fact_updated
    fact_id: Optional[str] = None
    old_value: Optional[dict[str, Any]] = None
    new_value: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None
