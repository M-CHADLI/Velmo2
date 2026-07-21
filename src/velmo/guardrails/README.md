# Guardrails Module

## Overview

The `guardrails` module provides input/output security guards for Velmo 2.0. It protects the agent by filtering harmful, out-of-scope, or malicious content at both ingestion and generation boundaries. All decisions are logged to PostgreSQL with latency metrics for observability and compliance auditing.

## Architecture

The guardrails flow follows a schema → rules → guards → classifier → manager → audit pattern:

1. **Schema** (`schema.py`): Defines `GuardDecision` dataclass and forbidden content categories (hate, violence, sexual, prompt_injection, secret_leak, out_of_scope). Also exports `SAFE_MESSAGE` — the polite deflection message shown to users when input is blocked.

2. **Rules & Guards** (`rules.py`, `input_guard.py`, `output_guard.py`): 
   - Static pattern matching and rule-based detection for common attack vectors
   - Input guard: checks user messages before processing
   - Output guard: validates agent responses before delivery
   - Returns early `GuardDecision(allowed=False, ...)` if any rule triggers

3. **Kimi Classifier** (`classifier.py`): Uses Kimi 2.6 via LangChain to categorize ambiguous content and make nuanced allow/block decisions. Receives a `GuardDecision` from rules and may override it based on semantic analysis.

4. **Manager** (`manager.py`): Orchestrates input/output checks via `check_input(message, user_id)` and `check_output(response, user_id)`. Routes decisions to audit logging and returns the final `GuardDecision`.

5. **Audit Logging** (`audit.py`): Writes all decisions to PostgreSQL `guardrail_log` table (columns: user_id, where_, category, allowed, reason, latency_ms, created_at) without blocking on DB failures.

## LangFuse Integration

LangFuse observability is integrated automatically via LangChain's `CallbackHandler`. When `KimiClassifier` calls the Kimi 2.6 model, LangChain's built-in instrumentation:
- Captures the prompt, completion, and tokens
- Logs to the LangFuse backend configured in `memory.config.Settings` (via `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` env vars)
- Enables latency tracking and cost attribution

**No explicit LangFuse import or coupling in guardrails code** — the integration is transparent via LangChain callbacks. See `classifier.py` for LangChain setup.

## PostgreSQL Audit

The `guardrail_log` table schema:
```sql
CREATE TABLE guardrail_log (
    id          SERIAL PRIMARY KEY,
    user_id     VARCHAR(100) NOT NULL,
    where_      VARCHAR(10) NOT NULL,        -- "input" | "output"
    category    VARCHAR(50) NOT NULL,        -- "hate", "violence", etc.
    allowed     BOOLEAN NOT NULL,
    reason      TEXT,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_guardrail_log_user_id ON guardrail_log(user_id);
```

Audit logging is non-blocking: if the database is unavailable, a warning is logged but the decision is still returned to the user.

## Usage

```python
from guardrails import GuardrailManager, GuardDecision, SAFE_MESSAGE

# Initialize the manager (auto-loads Kimi classifier)
mgr = GuardrailManager()

# Check user input
decision = mgr.check_input("I have a question about my invoice", user_id="user_123")
if decision.allowed:
    # Safe to process the message
    process_message(...)
else:
    # Blocked — use the safe message
    return decision.safe_message

# Check agent output before delivering to user
output_decision = mgr.check_output(agent_response, user_id="user_123")
if output_decision.allowed:
    send_to_user(agent_response)
else:
    send_to_user(output_decision.safe_message or SAFE_MESSAGE)
```

## Testing

Run tests with:
```bash
pytest tests/test_guardrails*.py -v
```

Run the acceptance evaluation:
```bash
python eval_guardrails.py
```
