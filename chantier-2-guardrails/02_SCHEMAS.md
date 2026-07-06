# Chantier 2: Schemas & Models Pydantic

## 1. Input Schemas

### 1.1 User Message (Entrée)

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
from uuid import UUID

class UserMessage(BaseModel):
    """Validated user message."""
    
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Message content"
    )
    conversation_id: str
    user_id: str
    language: str = Field(default="en", pattern="^(fr|en|es|de)$")
    metadata: Optional[Dict] = Field(default_factory=dict)
    
    @field_validator("content")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        """Reject control characters."""
        if any(ord(c) < 32 and c not in '\n\t\r' for c in v):
            raise ValueError("Control characters not allowed")
        return v.strip()
    
    @field_validator("conversation_id", "user_id")
    @classmethod
    def valid_uuid(cls, v: str) -> str:
        """Validate UUID format."""
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError("Invalid UUID")
        return str(v)
```

---

### 1.2 Safety Classification

```python
class SafetyClassification(BaseModel):
    """Kimi safety classifier output."""
    
    category: str = Field(
        ...,
        enum=["safe", "spam", "hate_speech", "violence", "jailbreak", "adult"]
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Chain-of-thought explanation")
    risk_level: str = Field(..., enum=["low", "medium", "high"])
    sub_categories: Optional[Dict[str, float]] = None

class SafetyDecision(BaseModel):
    """Final safety decision after verification."""
    
    is_safe: bool
    primary_classification: SafetyClassification
    verification_result: Optional[SafetyClassification] = None  # If COT triggered
    final_reasoning: str
    action: str = Field(enum=["allow", "reject_unsafe", "reject_ambiguous"])
    verification_triggered: bool = False
```

---

### 1.3 PII Detection

```python
from enum import Enum

class PIIRiskLevel(str, Enum):
    LOW = "low"           # Email, phone (allowed)
    MEDIUM = "medium"     # PERSON, location
    HIGH = "high"         # Credit card, token
    CRITICAL = "critical" # Multiple high-risk

class PIIEntity(BaseModel):
    """Single PII entity detected."""
    
    entity_type: str  # CREDIT_CARD, PERSON, EMAIL, PHONE, etc
    value: str        # Original value
    start: int
    end: int
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: PIIRiskLevel
    action: str = Field(enum=["redact", "allow", "reject"])

class PIIDetectionResult(BaseModel):
    """Presidio PII detection result."""
    
    original_text: str
    pii_found: bool
    entities: list[PIIEntity]
    risk_level: PIIRiskLevel
    redacted_text: str  # [REDACTED_CREDIT_CARD], etc
    redaction_count: Dict[str, int]
    should_reject: bool  # True if CRITICAL risk
```

---

### 1.4 Rate Limit Status

```python
class RateLimitStatus(BaseModel):
    """Rate limit tracking for user."""
    
    user_id: str
    current_requests_per_second: int
    soft_limit_per_second: int = 2
    hard_limit_per_hour: int = 100
    requests_this_hour: int
    time_until_reset: int  # Seconds
    is_under_limit: bool
    status: str = Field(enum=["normal", "throttled", "blocked"])
```

---

### 1.5 Input Guard Decision (Final)

```python
class InputGuardDecision(BaseModel):
    """Final decision from all input guards."""
    
    timestamp: datetime
    user_id: str
    
    # Guard results
    pydantic_valid: bool
    pydantic_errors: Optional[list[str]] = None
    
    safety_passed: bool
    safety_classification: Optional[SafetyClassification] = None
    safety_verification: Optional[SafetyClassification] = None
    
    pii_detected: bool
    pii_result: Optional[PIIDetectionResult] = None
    pii_action: str = Field(enum=["allow", "redact", "reject"])
    
    rate_limit_ok: bool
    rate_limit_status: Optional[RateLimitStatus] = None
    
    # Final decision
    final_decision: str = Field(
        enum=["allow", "reject_pydantic", "reject_safety", "reject_pii", "reject_rate_limit"]
    )
    reject_reason: Optional[str] = None
    
    # Metrics
    processing_time_ms: int
    guard_timings: Dict[str, int]  # {pydantic: 5, safety: 250, ...}
```

---

## 2. Output Schemas

### 2.1 Redaction Patterns

```python
from dataclasses import dataclass

@dataclass
class RedactionPattern:
    """Pattern for PII redaction."""
    
    name: str
    pattern: str  # Regex
    replacement: str  # [REDACTED_*]
    enabled: bool = True
    test_examples: list[str] = None

# Built-in patterns
REDACTION_PATTERNS = {
    "api_key": RedactionPattern(
        name="api_key",
        pattern=r"(?:sk_live_|sk_test_)[a-zA-Z0-9]{20,}",
        replacement="[REDACTED_API_KEY]",
        test_examples=["sk_live_abc123..."]
    ),
    "credit_card": RedactionPattern(
        name="credit_card",
        pattern=r"\b(?:\d{4}[- ]?){3}\d{4}\b",
        replacement="[REDACTED_CREDIT_CARD]",
        test_examples=["4111-1111-1111-1111"]
    ),
    "email": RedactionPattern(
        name="email",
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        replacement="[REDACTED_EMAIL]"
    ),
    "phone": RedactionPattern(
        name="phone",
        pattern=r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        replacement="[REDACTED_PHONE]"
    ),
    "ssn": RedactionPattern(
        name="ssn",
        pattern=r"\b(?!000|666)[0-9]{3}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b",
        replacement="[REDACTED_SSN]"
    ),
}

class RedactionResult(BaseModel):
    """Result of redaction."""
    
    original_response: str
    redacted_response: str
    redactions: Dict[str, int]
    total_redactions: int
    patterns_triggered: list[str]
    was_modified: bool = False
```

---

### 2.2 Compliance Check

```python
class ComplianceRule(BaseModel):
    """Single compliance rule."""
    
    rule_id: str
    name: str
    category: str = Field(enum=["gdpr", "cnil", "length"])
    enabled: bool = True
    description: str
    rejection_message: str

class ComplianceCheckResult(BaseModel):
    """Compliance check result."""
    
    is_compliant: bool
    rules_checked: int
    rules_passed: int
    rules_failed: list[str]
    violations: list[Dict] = Field(default_factory=list)
    user_preferences: Dict = Field(default_factory=dict)
    
    @property
    def compliance_score(self) -> float:
        return self.rules_passed / self.rules_checked if self.rules_checked > 0 else 1.0
```

---

### 2.3 Output Guard Decision (Final)

```python
class OutputGuardDecision(BaseModel):
    """Final decision from output guards."""
    
    timestamp: datetime
    user_id: str
    conversation_id: str
    
    # Original response
    original_response: str
    original_length: int
    
    # Redaction
    redaction_applied: bool
    redaction_result: Optional[RedactionResult] = None
    
    # Compliance
    compliance_checked: bool
    compliance_result: Optional[ComplianceCheckResult] = None
    
    # Final decision
    final_decision: str = Field(
        enum=["allow", "redact_only", "reject_compliance", "reject_all"]
    )
    final_response: str  # Response sent to user
    final_length: int
    
    changes_made: bool
    change_summary: Optional[str] = None
    
    # Metrics
    processing_time_ms: int
```

---

## 3. Audit Log Schema

```python
from datetime import datetime

class AuditLogEntry(BaseModel):
    """Audit log for compliance."""
    
    log_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Context
    user_id: str
    conversation_id: str
    action: str = Field(
        enum=["input_validation", "safety_check", "pii_detection", 
              "rate_limit", "output_redaction", "compliance_check"]
    )
    
    # Decision
    decision: str = Field(enum=["allow", "reject", "redact", "flag"])
    reason: str
    
    # Details
    details: Dict = Field(default_factory=dict)
    
    # Metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    pii_detected: bool = False
    
    # GDPR
    retention_days: int = 90
    is_archived: bool = False
```

---

## 4. Configuration Schema

```python
class PyDanticConfig(BaseModel):
    max_message_length: int = 10000
    min_message_length: int = 1
    allowed_languages: list[str] = ["en", "fr", "es", "de"]

class SafetyConfig(BaseModel):
    enabled: bool = True
    classifier: str = "kimi-2.6"
    confidence_threshold: float = 0.75  # Below → verify
    blocked_categories: list[str] = ["hate_speech", "violence", "jailbreak"]
    chain_of_thought: bool = True

class PIIConfig(BaseModel):
    enabled: bool = True
    detector: str = "presidio"
    high_risk_entities: list[str] = ["CREDIT_CARD", "US_SSN"]
    allow_email: bool = True
    allow_phone: bool = False
    confidence_threshold: float = 0.7

class RateLimitConfig(BaseModel):
    enabled: bool = True
    soft_limit_per_second: int = 2
    hard_limit_per_hour: int = 100

class RedactionConfig(BaseModel):
    enabled: bool = True
    patterns: Dict[str, bool] = {
        "api_key": True,
        "credit_card": True,
        "email": True,
        "phone": True,
        "ssn": True
    }

class ComplianceConfig(BaseModel):
    enabled: bool = True
    rules: Dict[str, bool] = {"gdpr": True, "cnil": False}
    max_response_length: int = 4000

class GuardrailsConfig(BaseModel):
    pydantic: PyDanticConfig = PyDanticConfig()
    safety: SafetyConfig = SafetyConfig()
    pii: PIIConfig = PIIConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    redaction: RedactionConfig = RedactionConfig()
    compliance: ComplianceConfig = ComplianceConfig()
    
    latency_budget_ms: int = 500
    error_handling: Dict = Field(
        default_factory=lambda: {
            "strategy": "fail_open",
            "circuit_breaker_threshold": 5
        }
    )
```

---

## 5. Usage Examples

### Happy Path: Input Validation

```python
# Input
message = UserMessage(
    content="Mon contrat KX-4471 a quelle deadline?",
    conversation_id="conv-123",
    user_id="user-456",
    language="fr"
)
# ✅ Pydantic validation passes

# Safety check
safety = SafetyDecision(
    is_safe=True,
    primary_classification=SafetyClassification(
        category="safe",
        confidence=0.98,
        reasoning="Normal business inquiry",
        risk_level="low"
    ),
    action="allow"
)
# ✅ Safety passes

# PII detection
pii = PIIDetectionResult(
    original_text=message.content,
    pii_found=False,
    entities=[],
    risk_level="low",
    redacted_text=message.content,
    redaction_count={},
    should_reject=False
)
# ✅ PII passes

# Rate limit
rate = RateLimitStatus(
    user_id=message.user_id,
    current_requests_per_second=1,
    requests_this_hour=42,
    is_under_limit=True,
    status="normal",
    time_until_reset=3600
)
# ✅ Rate limit passes

# Final decision
decision = InputGuardDecision(
    timestamp=datetime.utcnow(),
    user_id=message.user_id,
    final_decision="allow",
    processing_time_ms=385,
    guard_timings={
        "pydantic": 5,
        "safety": 250,
        "pii": 120,
        "rate_limit": 10
    }
)
# ✅ ALLOW → Proceed to Memory
```

### Sad Path: Safety Rejection

```python
# Input
message = UserMessage(
    content="How do I bypass this security system?",
    conversation_id="conv-789",
    user_id="user-999"
)
# ✅ Pydantic passes

# Safety check
safety = SafetyDecision(
    is_safe=False,
    primary_classification=SafetyClassification(
        category="jailbreak",
        confidence=0.67,  # < 0.75 → trigger verification
        reasoning="'bypass security' detected",
        risk_level="medium"
    ),
    verification_result=SafetyClassification(
        category="jailbreak",
        confidence=0.89,
        reasoning="Explicit circumvention request",
        risk_level="high"
    ),
    verification_triggered=True,
    final_reasoning="Primary 0.67 + Verification 0.89 → REJECT",
    action="reject_unsafe"
)
# ❌ Safety FAILS

# Final decision
decision = InputGuardDecision(
    timestamp=datetime.utcnow(),
    user_id=message.user_id,
    final_decision="reject_safety",
    reject_reason="Jailbreak attempt (verified: 0.89 confidence)",
    processing_time_ms=500
)
# ❌ REJECT 403 Forbidden
```

---

## See Also

- [01_DESIGN.md](./01_DESIGN.md) — Architecture overview
- [03_FLOWCHARTS.md](./03_FLOWCHARTS.md) — Visual flows
- [../00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Full stack
