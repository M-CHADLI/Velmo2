# Chantier 2: Optimisations & Parallélisation

## Latency Gains

| Optimisation | Before | After | Gain |
|---|---|---|---|
| **Sequential** | 540ms | 260ms | **-280ms (-52%)** |
| + Cache Safety (25% req) | 540ms | 390ms avg | **-150ms** |
| + Streaming G1 | Perceived 2525ms | Perceived 50ms | **-2475ms** |

---

## 1. Parallélisation (Guard 2,3,4)

**Implémentation:**
```python
async def validate_input(message: UserMessage) -> InputGuardDecision:
    # Guard 1: MUST run first
    pydantic_result = await guard_pydantic(message)
    if not pydantic_result.is_valid:
        return reject()
    
    # Guards 2,3,4: Parallel
    safety_task = asyncio.create_task(guard_safety(message))
    pii_task = asyncio.create_task(guard_pii(message))
    rate_limit_task = asyncio.create_task(guard_rate_limit(user_id))
    
    # Wait for all
    safety_result = await safety_task      # ~250ms
    pii_result = await pii_task            # ~120ms
    rate_limit_result = await rate_limit_task  # ~10ms
    
    # Max of above = 250ms instead of 380ms
    
    # Guard 5: Audit (must be last)
    audit_log = await guard_audit(...)
    
    return final_decision()  # Total: ~260ms
```

---

## 2. Early Exit

**Before:**
- Invalid format → Still run all 5 guards (waste 535ms)

**After:**
- Invalid format → Reject immediately at Guard 1
- Saves: **280-530ms**

---

## 3. Safety Cache (Optional)

**Mechanism:**
```python
SAFETY_CACHE = Redis(ttl=5min)

safety_result = SAFETY_CACHE.get(hash(message))
if safety_result:
    return safety_result  # -250ms!

safety_result = await kimi_classify(message)
SAFETY_CACHE.set(hash(message), safety_result, ttl=300)
```

**Impact:**
- ~25% of requests get cache hit
- **-250ms per cached request**
- Requires de-duplication logic

---

## 4. Streaming First Token

**Mechanism:**
```python
# Send to Memory immediately after Guard 1 ✅
if pydantic_valid:
    memory_queue.push(message)  # Start processing
    
# Meanwhile, Guards 2,3,4 run in background
# If any fails → cancel and send error
```

**Impact:**
- User perceives **only 5ms** (first Guard)
- Guards 2,3,4 run async in background
- **-2475ms perceived latency!**

---

## 5. Batch Audit Logging

**Before:**
```python
for each message:
    INSERT INTO audit_log ...  # 5ms per request
```

**After:**
```python
batch_queue = []
for each message:
    batch_queue.append(log_entry)
    if len(batch_queue) >= 100:
        INSERT INTO audit_log (SELECT ...) VALUES (...)  # 1 query for 100
        batch_queue = []
```

**Impact:**
- 100 logs in 1 query instead of 100 queries
- **-3-4ms per request on average**

---

## 6. COT on Demand (Tuning)

**Before:**
- Trigger COT if confidence < 0.75
- ~30% of requests hit COT
- +150ms per COT

**After:**
- Trigger COT only if 0.5 < confidence < 0.75 (truly ambiguous)
- ~8% of requests hit COT
- **-110ms on average** (22% fewer COTs)

---

## Latency Timeline (Optimized)

```
t=0ms:   Message arrives
t=5ms:   Guard 1 ✅ → Send to Memory (streaming)
t=5-255ms: Guards 2,3,4 run in parallel
t=255ms: All guards done
t=260ms: Audit log → ALLOW
t=260-260ms: Message in Memory (started already)
t=2440ms: LLM response ready
t=2525ms: User receives response
```

**New SLA:**
- Input guards: **260ms** (was 540ms)
- Perceived latency: **50ms** (with streaming)
- Total: **2525ms** unchanged (LLM dominates)

---

## Implementation Checklist

- [ ] Convert guards to async/await
- [ ] Implement asyncio.gather for G2,3,4
- [ ] Add Redis cache for Safety
- [ ] Setup message streaming to Memory
- [ ] Batch audit logs every 100 entries
- [ ] Tune COT threshold (0.5-0.75)
- [ ] Update monitoring dashboards

