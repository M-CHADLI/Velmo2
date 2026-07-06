# Chantier 2: Design Détaillé (Guardrails)

## Vue d'Ensemble

Chantier 2 protège Velmo sur deux fronts:

1. **Input Guards** — Valider, nettoyer, filtrer les messages entrants
2. **Output Guards** — Redacter, vérifier la conformité des réponses

---

## 1. Input Guards (5 Étapes)

### 1.1 Validation de Schéma (Pydantic)

```python
from pydantic import BaseModel, Field, validator

class UserMessage(BaseModel):
    """Validate incoming message format."""
    
    content: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str
    user_id: str
    language: str = Field(default="en", regex="^(fr|en|es|de)$")
    metadata: dict = {}
    
    @validator("content")
    def no_control_chars(cls, v):
        """Reject control characters."""
        if any(ord(c) < 32 and c not in '\n\t\r' for c in v):
            raise ValueError("Control characters not allowed")
        return v
    
    @validator("conversation_id", "user_id")
    def valid_uuid(cls, v):
        """Validate UUID format."""
        try:
            UUID(v)
        except:
            raise ValueError("Invalid UUID format")
        return v
```

**Decision Points**:
- ✅ Format valide? → Continue
- ❌ Format invalide? → REJECT + audit log

---

### 1.2 Safety Classification (Kimi)

Classifie le contenu pour détecter:
- Spam, hate speech, violence
- Jailbreak attempts
- Adult content

```python
def classify_safety(message: str) -> dict:
    """Use Kimi as safety classifier."""
    
    prompt = f"""Classify this message for safety risks:
    
Message: "{message}"

Respond with JSON:
{{
  "category": "safe" | "spam" | "hate_speech" | "violence" | "jailbreak" | "adult",
  "confidence": 0.0-1.0,
  "reason": "Brief explanation"
}}

Output JSON only."""
    
    response = llm.invoke(prompt)
    result = json.loads(response.content)
    
    return result["category"] != "safe" or result["confidence"] < 0.7
```

**Decision Points**:
- ✅ Safe? → Continue
- ❌ Unsafe? → REJECT + alert

---

### 1.3 PII Detection (Presidio)

Détecte informations sensibles (cartes bancaires, SSN, emails, téléphones).

```python
from presidio_analyzer import AnalyzerEngine
from presidio_redactor import RedactorEngine

analyzer = AnalyzerEngine()
redactor = RedactorEngine()

def scan_pii(text: str) -> dict:
    """Detect PII in text."""
    
    results = analyzer.analyze(
        text=text,
        languages=["en", "fr"]
    )
    
    pii_found = {}
    for result in results:
        entity_type = result.entity_type
        if entity_type not in pii_found:
            pii_found[entity_type] = []
        
        pii_found[entity_type].append({
            "value": text[result.start:result.end],
            "confidence": result.score
        })
    
    # Optionally redact
    redacted_text = redactor.redact(text)
    
    return {
        "pii_detected": len(results) > 0,
        "entities": pii_found,
        "redacted_text": redacted_text
    }
```

**Decision Points**:
- ✅ No PII? → Continue
- ⚠️ PII found? → Log + Continue (context-aware, allow unless high-risk)
- ❌ High-risk PII? → REJECT

---

### 1.4 Rate Limiting (Redis)

Limiter par user: max 100 req/heure.

```python
import redis
from datetime import datetime, timedelta

redis_client = redis.Redis(host='localhost', port=6379)

def check_rate_limit(user_id: str, limit: int = 100, window: int = 3600) -> bool:
    """Check if user exceeded rate limit."""
    
    key = f"rate_limit:{user_id}"
    current_count = redis_client.incr(key)
    
    if current_count == 1:
        # First request, set expiry
        redis_client.expire(key, window)
    
    return current_count <= limit
```

**Decision Points**:
- ✅ Under limit? → Continue
- ❌ Over limit? → REJECT (429 Too Many Requests)

---

### 1.5 Audit Logging

```python
def audit_log_input(
    user_id: str,
    action: str,
    decision: str,  # allow, reject_pydantic, reject_safety, reject_rate
    reason: str,
    pii_detected: bool,
    ip_address: str
):
    """Log input validation decision."""
    
    db.audit_log.insert({
        "user_id": user_id,
        "action": action,
        "decision": decision,
        "reason": reason,
        "pii_detected": pii_detected,
        "ip_address": ip_address,
        "timestamp": datetime.utcnow()
    })
```

---

## 2. Output Guards (2 Étapes)

### 2.1 PII Redaction

Redacter les secrets que Kimi aurait pu générer.

```python
import re

REDACTION_PATTERNS = {
    "api_key": r"(?:sk_live_|sk_test_)[a-zA-Z0-9]{20,}",
    "token": r"(?:ghp_|github_pat_)[a-zA-Z0-9]{36,}",
    "credit_card": r"\b(?:\d{4}[- ]?){3}\d{4}\b",  # 16 digits
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
}

def redact_secrets(response: str) -> dict:
    """Redact sensitive patterns from LLM response."""
    
    redacted = response
    found_secrets = {}
    
    for secret_type, pattern in REDACTION_PATTERNS.items():
        matches = re.findall(pattern, response)
        if matches:
            found_secrets[secret_type] = len(matches)
            redacted = re.sub(pattern, f"[REDACTED_{secret_type.upper()}]", redacted)
    
    return {
        "original_length": len(response),
        "redacted_length": len(redacted),
        "secrets_found": found_secrets,
        "redacted_text": redacted
    }
```

---

### 2.2 Compliance Check

Vérifier que la réponse respect les règles GDPR/CNIL.

```python
def check_compliance(response: str, user_preferences: dict) -> bool:
    """Check output for compliance with user preferences."""
    
    # GDPR rules
    if user_preferences.get("no_profiling", False):
        if "profile" in response.lower() or "analysis" in response.lower():
            return False, "Violates no_profiling preference"
    
    # CNIL rules (France)
    if user_preferences.get("french_resident", False):
        if "data_transfer" in response.lower():
            return False, "Violates CNIL data residency"
    
    # Length limits
    max_length = user_preferences.get("max_response_length", 4000)
    if len(response) > max_length:
        return False, f"Response exceeds max length {max_length}"
    
    return True, "Compliance check passed"
```

---

## 3. Full Input-Output Flow

```
User Input
  ↓
[1. Pydantic Validation]
  ├─ Format OK? ─NO→ REJECT (400 Bad Request)
  └─ YES ↓
[2. Safety Check (Kimi)]
  ├─ Safe? ─NO→ REJECT (403 Forbidden)
  └─ YES ↓
[3. PII Detection (Presidio)]
  ├─ PII Found? ─YES→ LOG (context-aware, continue)
  └─ NO/Logged ↓
[4. Rate Limit (Redis)]
  ├─ Under limit? ─NO→ REJECT (429 Too Many)
  └─ YES ↓
[5. Audit Log]
  └─ Log: ALLOW
      ↓
  → Chantier 1 (Memory Processing)
      ↓
  LLM Response Generated
      ↓
[1. PII Redaction]
  └─ Redact: API keys, tokens, emails, etc.
      ↓
[2. Compliance Check]
  ├─ Compliant? ─NO→ Return safe error message
  └─ YES ↓
[3. Audit Log]
  └─ Log: Output decision
      ↓
  → User Response
```

---

## 4. Configuration

### Rules Engine (YAML)

```yaml
# guardrails.yaml
input_guards:
  pydantic:
    max_message_length: 10000
    min_message_length: 1
    allowed_languages: [en, fr, es, de]
  
  safety:
    enabled: true
    classifier: kimi-2.6
    confidence_threshold: 0.7
    blocked_categories: [hate_speech, violence, jailbreak]
    allow_spam: false
  
  pii:
    enabled: true
    detector: presidio
    high_risk_entities: [credit_card, ssn, token]
    allow_email: true
    allow_phone: false
  
  rate_limit:
    enabled: true
    storage: redis
    limit: 100
    window_seconds: 3600

output_guards:
  redaction:
    enabled: true
    patterns:
      - api_key
      - token
      - credit_card
      - email
      - phone
  
  compliance:
    enabled: true
    rules:
      gdpr: true
      cnil: true
      max_response_length: 4000
```

---

## 5. Metrics & Monitoring

### Guard Performance Metrics

```python
class GuardMetrics:
    """Track guard effectiveness."""
    
    def __init__(self):
        self.total_inputs = 0
        self.rejected_inputs = {
            "pydantic": 0,
            "safety": 0,
            "pii_high_risk": 0,
            "rate_limit": 0
        }
        self.total_outputs = 0
        self.redactions = {
            "api_key": 0,
            "token": 0,
            "credit_card": 0
        }
        self.rejected_outputs = 0
    
    def log_input(self, user_id: str, decision: str):
        """Log input decision."""
        self.total_inputs += 1
        if decision != "allow":
            self.rejected_inputs[decision] += 1
    
    def get_rejection_rate(self) -> float:
        """Get overall rejection rate."""
        total_rejected = sum(self.rejected_inputs.values())
        return total_rejected / self.total_inputs if self.total_inputs > 0 else 0.0

# Monitoring targets (SLA)
METRICS_TARGETS = {
    "rejection_rate_pydantic": 0.05,      # 5% invalid format
    "rejection_rate_safety": 0.02,        # 2% unsafe
    "rejection_rate_pii": 0.01,           # 1% high-risk PII
    "rejection_rate_rate_limit": 0.001,   # 0.1% rate limited
    "redaction_rate": 0.05,               # 5% of outputs have secrets
    "rejection_rate_compliance": 0.01     # 1% non-compliant output
}
```

---

## 6. Integration with Other Chantiers

**← Chantier 1**:
- Input guards applied before Memory.add()
- Output guards applied after LLM response
- Redacted facts never exposed

**→ Chantier 3**:
- Guard decisions logged in audit_log
- Metrics tracked for compliance monitoring
- Rejection rates used as quality signal

---

## See Also

- [02_SCHEMAS.md](./02_SCHEMAS.md) — Validation schemas
- [03_FLOWCHARTS.md](./03_FLOWCHARTS.md) — Input/Output guard flows
- [../00_STACK_GLOBALE.md](../00_STACK_GLOBALE.md) — Overall stack
