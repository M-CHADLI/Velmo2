# Chantier 2: Visual Flows & Diagrams

## 1. Input Guard Pipeline (Optimisé - Parallélisé)

```mermaid
graph TD
    A["🔵 User Message Arrives"] --> B["⚙️ Guard 1: Pydantic<br/>5ms"]
    
    B -->|✅ Valid| B_OK["Format OK"]
    B -->|❌ Invalid| B_FAIL["REJECT<br/>400 Bad Request"]
    
    B_OK --> PAR["⚡ PARALLEL EXECUTION"]
    
    PAR --> C["⚙️ Guard 2: Safety (Kimi)<br/>250ms"]
    PAR --> D["⚙️ Guard 3: PII (Presidio)<br/>120ms"]
    PAR --> E["⚙️ Guard 4: Rate Limit<br/>10ms"]
    
    C --> C_CONF{Confidence<br/>≥ 0.75?}
    C_CONF -->|YES| C_OK["✅ Safe"]
    C_CONF -->|NO| C_VERIFY["🔄 COT verify<br/>+150ms"]
    C_VERIFY --> C_OK
    C_CONF -->|NO (REJECT)| C_FAIL["❌ REJECT<br/>403"]
    
    D --> D_RISK{Risk?}
    D_RISK -->|CRITICAL| D_FAIL["❌ REJECT<br/>403"]
    D_RISK -->|HIGH/MEDIUM| D_REDACT["🔧 REDACT"]
    D_RISK -->|LOW| D_OK["✅ ALLOW"]
    D_REDACT --> D_OK
    
    E --> E_CHECK{Rate?}
    E_CHECK -->|OK| E_OK["✅ NORMAL"]
    E_CHECK -->|THROTTLE| E_THROTTLE["⏱️ +2sec"]
    E_CHECK -->|EXCEED| E_FAIL["❌ REJECT<br/>429"]
    E_THROTTLE --> E_OK
    
    C_OK --> SYNC["🔄 SYNC"]
    D_OK --> SYNC
    E_OK --> SYNC
    
    SYNC --> F["⚙️ Guard 5: Audit<br/>5ms"]
    F --> FINAL["✅✅ ALLOW<br/>Total: 260ms"]
    
    B_FAIL --> AUDIT["📋 Audit"]
    C_FAIL --> AUDIT
    D_FAIL --> AUDIT
    E_FAIL --> AUDIT
    AUDIT --> ERR_RESP["↩️ Error"]
    
    FINAL --> PROCEED["→ Chantier 1<br/>Memory"]
    
    style A fill:#e1f5ff
    style PAR fill:#c8e6c9
    style FINAL fill:#c8e6c9
    style PROCEED fill:#fff9c4
    style SYNC fill:#fff9c4
    style B_FAIL fill:#ffcdd2
    style C_FAIL fill:#ffcdd2
    style D_FAIL fill:#ffcdd2
    style E_FAIL fill:#ffcdd2
    style ERR_RESP fill:#ffcdd2
```

---

## 2. Output Guard Pipeline

```mermaid
graph TD
    A["🟢 LLM Response<br/>from Kimi"] --> B["⚙️ Guard 1: Redaction<br/>50ms"]
    
    B --> B_SCAN["Scan patterns:<br/>api_key, token<br/>credit_card, email<br/>phone, ssn"]
    
    B_SCAN --> B_FOUND{Secrets<br/>found?}
    B_FOUND -->|NO| B_OK["✅ No secrets"]
    B_FOUND -->|YES| B_REDACT["🔧 Replace with<br/>[REDACTED_*]"]
    
    B_REDACT --> B_TRACK["📊 Track<br/>api_key: 2<br/>email: 1"]
    
    B_TRACK --> C["⚙️ Guard 2: Compliance<br/>30ms"]
    
    C --> C_CHECK["Check rules:<br/>no_profiling<br/>data_residency<br/>max_response_length"]
    
    C_CHECK --> C_PASS{Compliant?}
    C_PASS -->|YES| C_OK["✅ Compliant"]
    C_PASS -->|NO| C_FAIL["REJECT<br/>Return safe error"]
    
    B_OK --> C
    
    C_OK --> D["⚙️ Guard 3: Audit Log<br/>5ms"]
    
    D --> D_LOG["📋 Log:<br/>redactions, compliance<br/>changes_made, timestamp"]
    
    D_LOG --> E{Response<br/>modified?}
    E -->|YES| E_MODIFIED["⚠️ Mark modified"]
    E -->|NO| E_CLEAN["✅ Original"]
    
    E_MODIFIED --> FINAL["✅✅ Output Safe<br/>Total: 85ms"]
    E_CLEAN --> FINAL
    
    C_FAIL --> AUDIT_FAIL["📋 Audit reject"]
    AUDIT_FAIL --> ERROR_MSG["↩️ Safe error msg:<br/>'Unable to complete'"]
    
    FINAL --> SEND["↩️ Send to user"]
    ERROR_MSG --> SEND
    
    style A fill:#c8e6c9
    style FINAL fill:#c8e6c9
    style SEND fill:#ffe0b2
    style C_FAIL fill:#ffcdd2
    style ERROR_MSG fill:#ffcdd2
```

---

## 3. Safety Classification: Chain-of-Thought

```mermaid
graph TD
    A["Message: 'How to bypass<br/>this security?'"] --> B["Primary Classifier<br/>Kimi"]
    
    B --> C["Output:<br/>category: jailbreak<br/>confidence: 0.67"]
    
    C --> D{Confidence<br/>≥ 0.75?}
    D -->|YES| E["✅ Accept<br/>Trust primary"]
    D -->|NO| F["🔄 Trigger Verification<br/>2nd opinion"]
    
    F --> G["Kimi (COT mode):<br/>'Analyze step by step...'"]
    
    G --> H["Reasoning:<br/>1. Contains 'bypass'<br/>2. Targets 'security'<br/>3. Explicit circumvention"]
    
    H --> I["Output:<br/>category: jailbreak<br/>confidence: 0.89<br/>reasoning: [detailed]"]
    
    I --> J["Compare:<br/>Primary: 0.67<br/>Verification: 0.89"]
    
    J --> K{Agreement?}
    K -->|Both reject| L["❌ REJECT<br/>confidence: 0.89"]
    K -->|Disagree| M["🤔 Ambiguous<br/>Reject (safe)"]
    
    E --> N["✅ ALLOW<br/>Low risk"]
    
    style A fill:#e1f5ff
    style L fill:#ffcdd2
    style M fill:#ffcdd2
    style N fill:#c8e6c9
    style F fill:#fff9c4
    style G fill:#ffe082
```

---

## 4. PII Detection with Presidio

```mermaid
graph TD
    A["Input: 'Mon numéro de carte<br/>4111-1111-1111-1111<br/>et email alice@test.com'"] --> B["Presidio Analyzer"]
    
    B --> C["Detected entities:<br/>1. CREDIT_CARD (0.98)<br/>2. EMAIL_ADDRESS (0.99)"]
    
    C --> D["Classify risks:<br/>1. HIGH (CREDIT_CARD)<br/>2. MEDIUM (EMAIL)"]
    
    D --> E{Action per<br/>entity?}
    
    E -->|CRITICAL| F["❌ REJECT"]
    E -->|HIGH| G["🔧 REDACT"]
    E -->|MEDIUM| H["📋 LOG"]
    E -->|LOW| I["✅ ALLOW"]
    
    F --> F_OUT["Message blocked"]
    G --> G_OUT["Original: 4111-1111-1111-1111<br/>Redacted: [REDACTED_CREDIT_CARD]<br/><br/>Original: alice@test.com<br/>Redacted: [REDACTED_EMAIL]"]
    
    G_OUT --> J["Send redacted to<br/>Judge/LLM"]
    H --> H_OUT["Log in audit_log<br/>Continue with redaction"]
    H_OUT --> J
    I --> I_OUT["Allow as-is"]
    I_OUT --> J
    
    style A fill:#e1f5ff
    style F_OUT fill:#ffcdd2
    style G_OUT fill:#fff9c4
    style J fill:#c8e6c9
    style F fill:#ffcdd2
    style G fill:#ffe082
```

---

## 5. Rate Limiting: Sliding Window

```mermaid
graph LR
    T0["T=0s<br/>Req 1"]
    T0 --> C1["Count: 1<br/>Status: ✅<br/>NORMAL"]
    
    C1 --> T05["T=0.5s<br/>Req 2"]
    T05 --> C2["Count: 2<br/>Status: ✅<br/>SOFT LIMIT HIT"]
    
    C2 --> T07["T=0.7s<br/>Req 3"]
    T07 --> C3["Count: 3<br/>Status: ⏱️<br/>THROTTLE<br/>+2sec delay"]
    
    C3 --> T11["T=1.1s<br/>Req 4"]
    T11 --> C4["Count: 4<br/>Status: ⏱️<br/>THROTTLE"]
    
    C4 --> T30["T=3.0s<br/>Req 5<br/>Window reset"]
    T30 --> C5["Count: 1<br/>Status: ✅<br/>NORMAL"]
    
    C5 --> HOUR["Per-hour: 5/100<br/>Status: ✅<br/>OK"]
    
    HOUR --> T3600["T=3600s<br/>Req 100<br/>Hour window"]
    T3600 --> C100["Count: 100/100<br/>Status: ✅<br/>AT LIMIT"]
    
    C100 --> T3605["T=3605s<br/>Req 101"]
    T3605 --> C101["Count: 101/100<br/>Status: ❌<br/>HARD REJECT<br/>429 Too Many"]
    
    style C1 fill:#c8e6c9
    style C2 fill:#c8e6c9
    style C3 fill:#fff9c4
    style C4 fill:#fff9c4
    style C5 fill:#c8e6c9
    style HOUR fill:#c8e6c9
    style C100 fill:#ffe082
    style C101 fill:#ffcdd2
```

---

## 6. Error Handling: Fail Open Strategy

```mermaid
graph TD
    A["Guard process:<br/>e.g., Kimi safety call"] --> B["Call external service"]
    
    B --> C{Response<br/>OK?}
    
    C -->|YES| D["✅ Use result"]
    C -->|NO| E["❌ Service error"]
    
    E --> F{Type?}
    F -->|Timeout| G["Fallback:<br/>regex heuristic"]
    F -->|Auth| H["Circuit breaker:<br/>disable 5min"]
    F -->|Parse| G
    
    G --> I["Run lightweight<br/>check"]
    H --> J["Accept all<br/>Degraded mode"]
    
    I --> K{Result?}
    K -->|Suspicious| L["🎯 REJECT<br/>Fail safe"]
    K -->|OK| M["✅ ALLOW<br/>Trade UX"]
    
    D --> N["✅ Proceed"]
    L --> O["↩️ Error"]
    M --> N
    
    style N fill:#c8e6c9
    style O fill:#ffcdd2
    style L fill:#ffcdd2
    style H fill:#fff9c4
```

---

## 7. Full Input→Output Flow

```mermaid
graph LR
    subgraph INPUT["🔵 INPUT<br/>Guards"]
        I["Pydantic<br/>Safety<br/>PII<br/>Rate Limit<br/>Audit"]
    end
    
    subgraph MEMORY["🟡 CHANTIER 1<br/>Memory"]
        M["Window<br/>Judge<br/>Persist"]
    end
    
    subgraph LLM["🤖 LLM<br/>Kimi"]
        L["Generate"]
    end
    
    subgraph OUTPUT["🟢 OUTPUT<br/>Guards"]
        O["Redaction<br/>Compliance<br/>Audit"]
    end
    
    INPUT -->|✅ Allow| MEMORY
    MEMORY --> LLM
    LLM --> OUTPUT
    OUTPUT -->|✅ Safe| USER["↩️ User"]
    
    INPUT -->|❌ Reject| AUDIT1["📋 Audit"]
    OUTPUT -->|❌ Reject| AUDIT2["📋 Audit"]
    
    AUDIT1 --> ERR["Error response"]
    AUDIT2 --> ERR
    ERR --> USER
    
    style INPUT fill:#e1f5ff
    style MEMORY fill:#fff9c4
    style LLM fill:#ffe0b2
    style OUTPUT fill:#c8e6c9
    style USER fill:#e0e0e0
```

---

## 8. Guard Decision Tree

```mermaid
graph TD
    START["Message arrives"]
    
    START --> G1{Pydantic<br/>valid?}
    G1 -->|NO| R1["❌ Reject"]
    G1 -->|YES| G2{Safety<br/>OK?}
    
    G2 -->|NO| R2["❌ Reject"]
    G2 -->|YES| G3{PII risk<br/>acceptable?}
    
    G3 -->|NO| R3["❌ Reject"]
    G3 -->|YES| G4{Rate limit<br/>OK?}
    
    G4 -->|NO| R4["❌ Reject"]
    G4 -->|YES| ALLOW["✅ Allow<br/>Proceed"]
    
    R1 --> AUDIT["📋 Audit log"]
    R2 --> AUDIT
    R3 --> AUDIT
    R4 --> AUDIT
    
    ALLOW --> MEMORY["→ Chantier 1"]
    AUDIT --> ERROR["↩️ Error"]
    
    style ALLOW fill:#c8e6c9
    style R1 fill:#ffcdd2
    style R2 fill:#ffcdd2
    style R3 fill:#ffcdd2
    style R4 fill:#ffcdd2
    style ERROR fill:#ffcdd2
    style MEMORY fill:#fff9c4
```

---

## 9. Latency Budget (Optimisé)

```mermaid
gantt
    title Input Guard Latency - Parallélisé (< 300ms target)
    dateFormat YYYY-MM-DD HH:mm:ss
    
    section Sequential
    Pydantic        :p, 2024-01-01 00:00:00, 5ms
    
    section Parallel
    Safety (Kimi)   :s, after p, 250ms
    PII (Presidio)  :pii, after p, 120ms
    Rate Limit      :r, after p, 10ms
    
    section Finalize
    Sync Point      :crit, after s, 1ms
    Audit           :a, after s, 5ms
    
    Total           :crit, 2024-01-01 00:00:00, 260ms
    Buffer          :buff, after a, 40ms
```

---

## 10. Configuration State Machine

```mermaid
stateDiagram-v2
    [*] --> INIT: Load config
    
    INIT --> VALIDATE: Validate schema
    VALIDATE --> OK: ✅ Valid
    VALIDATE --> ERR: ❌ Invalid
    
    OK --> RUNNING: Start guards
    ERR --> [*]
    
    RUNNING --> MONITOR: Collect metrics
    MONITOR --> CHECK: Health check
    
    CHECK --> OK_STATE: ✅ All healthy
    CHECK --> DEGRADE: ⚠️ Some guards down
    CHECK --> CRITICAL: 🚨 Critical failure
    
    OK_STATE --> MONITOR
    DEGRADE --> FALLBACK: Use fallback guards
    FALLBACK --> MONITOR
    CRITICAL --> ALERT: Alert team
    ALERT --> RECOVER: Admin action
    RECOVER --> RUNNING
    
    RUNNING --> [*]: Shutdown
```

---

## 11. Audit Trail Timeline

```mermaid
timeline
    title Audit Log Timeline (Single Turn)
    T0 : Input Guard Start
       : Pydantic validation (5ms)
    T5 : Pydantic OK
       : Safety check start (Kimi)
    T255 : Safety OK
           : PII detection start (Presidio)
    T375 : PII OK
           : Rate limit check
    T385 : All guards pass
           : Log input decision
           : → Proceed to Memory
    
    T400 : Memory processing
           : Judge trigger (5% turns)
    
    T1900 : Judge complete
            : Facts extracted
    
    T2000 : LLM processing
            : Generate response
    
    T3500 : LLM response
            : Output guards start
    
    T3550 : Redaction complete
            : Compliance check
    
    T3585 : Output guards pass
            : Log output decision
            : → Send to user
```

---

## See Also

- [02_SCHEMAS.md](./02_SCHEMAS.md) — Pydantic models
- [01_DESIGN.md](./01_DESIGN.md) — Architecture details
- [../SCHEMA_FLUX_COMPLET.md](../SCHEMA_FLUX_COMPLET.md) — Full end-to-end flow
