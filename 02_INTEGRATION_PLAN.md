# VELMO 2.0 — Plan d'Intégration Complète

Étapes pour assembler l'architecture Velmo avec LangChain, Kimi 2.6, et observabilité.

---

## Phase 1: Setup Infrastructure (Foundations)

### 1.1 PostgreSQL + pgvector

```bash
# Install PostgreSQL 15+ with pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Create schema
CREATE SCHEMA IF NOT EXISTS velmo;

# Create facts table (Chantier 1)
CREATE TABLE velmo.facts (
    fact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,
    type VARCHAR(50),
    confidence FLOAT,
    embedding vector(3072),
    version_history JSONB,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT facts_user_id_idx UNIQUE(user_id, key)
);

# Create audit table (Chantier 2)
CREATE TABLE velmo.audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(100),
    decision VARCHAR(20),  -- 'allow' | 'reject'
    reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

# Create extraction metadata table (Chantier 1)
CREATE TABLE velmo.extraction_metadata (
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    round_number INT,
    messages_analyzed INT,
    judge_model VARCHAR(100),
    duration_ms INT,
    facts_created INT,
    facts_updated INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 1.2 Pinecone Setup

```bash
# Create Pinecone index
PINECONE_PROJECT=velmo-2.0
PINECONE_INDEX=facts
PINECONE_DIMENSION=3072  # text-embedding-3-large
PINECONE_METRIC=cosine

# Initialize via API (or UI)
curl -X POST https://api.pinecone.io/indexes \
  -H "Api-Key: $PINECONE_API_KEY" \
  -d '{
    "name": "facts",
    "dimension": 3072,
    "metric": "cosine"
  }'
```

### 1.3 Redis Setup

```bash
# Local or cloud Redis
redis-cli CONFIG SET maxmemory 1gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Test
redis-cli PING  # Should return PONG
```

### 1.4 LangSmith Setup

```bash
# Go to https://smith.langchain.com
# Create account + API key
# Set env vars

export LANGCHAIN_API_KEY="ls_prod_xxx"
export LANGCHAIN_PROJECT="Velmo-2.0"
export LANGCHAIN_TRACING_V2="true"
```

---

## Phase 2: Environment Configuration

### 2.1 .env File

```env
# Azure OpenAI (Kimi 2.6)
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://eagwu-0283-resource.services.ai.azure.com/
AZURE_OPENAI_DEPLOYMENT=kimi-2.6
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# OpenAI (for embeddings)
OPENAI_API_KEY=your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Pinecone
PINECONE_API_KEY=your-key-here
PINECONE_ENVIRONMENT=production
PINECONE_INDEX=facts

# PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost:5432/velmo
DB_SCHEMA=velmo

# Redis
REDIS_URL=redis://localhost:6379/0

# LangSmith
LANGCHAIN_API_KEY=your-key-here
LANGCHAIN_PROJECT=Velmo-2.0
LANGCHAIN_TRACING_V2=true

# Presidio (optional: local PII detection)
PRESIDIO_ENDPOINT=http://localhost:8000
```

### 2.2 Load Environment

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Verify all keys loaded
required_keys = [
    "AZURE_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "LANGCHAIN_API_KEY"
]

for key in required_keys:
    if not os.getenv(key):
        raise ValueError(f"Missing environment variable: {key}")
```

---

## Phase 3: LangChain Setup

### 3.1 Initialize LLM (Kimi 2.6)

```python
import os
from langchain.chat_models import AzureChatOpenAI
from langchain.callbacks import LangSmithTracer

# Azure OpenAI (Kimi 2.6)
llm = AzureChatOpenAI(
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0.7,
    max_tokens=2048
)

# Test it
response = llm.invoke("Say hello!")
print(response)
```

### 3.2 Initialize Embedding

```python
from langchain.embeddings.openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model=os.getenv("OPENAI_EMBEDDING_MODEL"),
    api_key=os.getenv("OPENAI_API_KEY")
)

# Test it
test_embedding = embeddings.embed_query("test")
print(f"Embedding dimension: {len(test_embedding)}")  # Should be 3072
```

### 3.3 Initialize Memory (Short-term)

```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(
    k=30,  # Keep last 30 messages
    return_messages=True,
    memory_key="chat_history"
)

# Test it
memory.save_context(
    {"input": "Hello, I'm Karim"},
    {"output": "Hi Karim! How can I help?"}
)
```

### 3.4 Initialize Vector Store (Pinecone)

```python
from langchain.vectorstores import Pinecone
from pinecone import Pinecone as PineconeClient

# Initialize Pinecone
pc = PineconeClient(
    api_key=os.getenv("PINECONE_API_KEY"),
    environment=os.getenv("PINECONE_ENVIRONMENT")
)

# Get or create index
index_name = os.getenv("PINECONE_INDEX")
vectorstore = Pinecone.from_existing_index(
    index_name=index_name,
    embedding=embeddings,
    namespace="default"
)

# Test it
results = vectorstore.similarity_search("contract", k=5)
print(f"Found {len(results)} similar documents")
```

---

## Phase 4: Judge Agent Setup (Chantier 1)

### 4.1 Define Judge Tools

```python
from langchain.tools import Tool
from langchain.agents import initialize_agent, AgentType
from typing import Dict, List
import json
from datetime import datetime

# Tool 1: Extract facts
def extract_facts_tool(messages: str) -> str:
    """Extract structured facts from messages."""
    prompt = f"""
    Analyze these messages and extract key facts:
    
    {messages}
    
    Return JSON:
    {{
      "facts": [
        {{
          "key": "contract_id",
          "value": "KX-4471",
          "type": "identifier",
          "confidence": 0.95,
          "source": "user_statement"
        }},
        ...
      ]
    }}
    """
    response = llm.invoke(prompt)
    return response.content

# Tool 2: Embed facts
def embed_facts_tool(facts_json: str) -> str:
    """Generate embeddings for facts."""
    facts = json.loads(facts_json)
    embedded = []
    
    for fact in facts.get("facts", []):
        vector = embeddings.embed_query(f"{fact['key']}: {fact['value']}")
        embedded.append({
            "fact_key": fact["key"],
            "vector_dim": len(vector)
        })
    
    return json.dumps({
        "embedded_count": len(embedded),
        "embeddings": embedded
    })

# Tool 3: Persist facts
def persist_facts_tool(facts_json: str) -> str:
    """Save facts to PostgreSQL + Pinecone."""
    # Implementation in Chantier 1 details
    return json.dumps({"status": "persisted", "count": 3})

# Register tools
tools = [
    Tool(
        name="ExtractFacts",
        func=extract_facts_tool,
        description="Extract structured facts from conversation messages"
    ),
    Tool(
        name="EmbedFacts",
        func=embed_facts_tool,
        description="Generate embeddings for extracted facts"
    ),
    Tool(
        name="PersistFacts",
        func=persist_facts_tool,
        description="Save facts to PostgreSQL and Pinecone"
    )
]

# Initialize Judge agent
judge_agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    callbacks=[LangSmithTracer(project_name="Velmo-2.0")]
)
```

### 4.2 Judge Trigger Logic

```python
class VelmoMemory:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.message_count = 0
        self.memory = memory
        self.judge_agent = judge_agent
    
    def add_message(self, role: str, content: str):
        """Add message to short-term window."""
        self.message_count += 1
        self.memory.save_context(
            {"input": content if role == "user" else ""},
            {"output": content if role == "assistant" else ""}
        )
        
        # Trigger judge every 10 messages
        if self.message_count % 10 == 0:
            self.trigger_judge()
    
    def trigger_judge(self):
        """Extract facts every 10 messages."""
        last_10_msgs = self.memory.buffer[-10:]  # Get last 10
        
        result = self.judge_agent.run(
            f"Extract facts from: {last_10_msgs}"
        )
        print(f"Judge extraction result: {result}")
        # Result is traced in LangSmith automatically
```

---

## Phase 5: Main QA Chain (Chantier 1 + LLM)

### 5.1 Retrieval Chain

```python
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

# Custom prompt with fact context
prompt_template = """
You are a helpful AI support agent. Use the facts below to answer the user.

Facts (from memory):
{context}

User: {question}

Answer:
"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["context", "question"]
)

# Initialize QA chain
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=vectorstore.as_retriever(
        search_kwargs={"k": 5}
    ),
    prompt=prompt,
    verbose=True,
    callbacks=[LangSmithTracer(project_name="Velmo-2.0")]
)
```

### 5.2 Main Processing Loop

```python
def process_user_message(user_id: str, message: str) -> str:
    """
    Main flow: Guardrails → Memory → Judge → LLM → Guardrails
    """
    # Chantier 2: Input guardrails
    if not validate_input(message):
        return "Invalid input format"
    
    if not check_content_safety(message):
        return "Message contains unsafe content"
    
    # Chantier 1: Memory
    velmo_mem = VelmoMemory(user_id)
    velmo_mem.add_message("user", message)
    
    # Chantier 1: Retrieval + LLM
    response = qa_chain.run(
        question=message,
        user_id=user_id
    )
    
    # Chantier 2: Output guardrails
    response = redact_pii(response)
    
    if not check_compliance(response):
        return "Output violates compliance rules"
    
    velmo_mem.add_message("assistant", response)
    
    return response
```

---

## Phase 6: Chantier 2 Integration (Guardrails)

### 6.1 Input Validation (Pydantic)

```python
from pydantic import BaseModel, validator

class UserMessage(BaseModel):
    user_id: str
    message: str
    timestamp: datetime
    
    @validator("message")
    def message_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v
    
    @validator("user_id")
    def user_id_valid(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Invalid user_id")
        return v

def validate_input(message: str) -> bool:
    """Validate message schema."""
    try:
        UserMessage(
            user_id="test-user",
            message=message,
            timestamp=datetime.now()
        )
        return True
    except ValueError:
        return False
```

### 6.2 Content Safety (Kimi Classifier)

```python
def check_content_safety(message: str) -> bool:
    """Use Kimi to classify message safety."""
    safety_prompt = f"""
    Classify this message:
    "{message}"
    
    Output ONLY: safe | spam | hate | violence
    """
    
    response = llm.invoke(safety_prompt)
    classification = response.content.strip().lower()
    
    return classification == "safe"
```

### 6.3 PII Detection (Presidio)

```python
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

def detect_pii(text: str) -> List[Dict]:
    """Detect PII entities."""
    results = analyzer.analyze(text=text, language="en")
    return [
        {
            "type": r.entity_type,
            "start": r.start,
            "end": r.end,
            "score": r.score
        }
        for r in results
    ]

def redact_pii(text: str) -> str:
    """Redact PII from text."""
    results = detect_pii(text)
    
    # Sort by position (reverse) to avoid index shift
    for result in sorted(results, key=lambda x: x["start"], reverse=True):
        start, end = result["start"], result["end"]
        text = text[:start] + "[REDACTED]" + text[end:]
    
    return text
```

### 6.4 Rate Limiting (Redis)

```python
import redis
from datetime import timedelta

redis_client = redis.from_url(os.getenv("REDIS_URL"))

def check_rate_limit(user_id: str, max_requests: int = 100) -> bool:
    """Check rate limit: max 100 requests per hour per user."""
    key = f"rate_limit:{user_id}"
    current = redis_client.incr(key)
    
    if current == 1:
        redis_client.expire(key, 3600)  # 1 hour
    
    return current <= max_requests
```

### 6.5 Audit Logging

```python
import psycopg2
from datetime import datetime

def log_audit(user_id: str, action: str, decision: str, reason: str = None):
    """Log all actions for compliance."""
    with psycopg2.connect(os.getenv("DATABASE_URL")) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO velmo.audit_log 
            (user_id, action, decision, reason, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, action, decision, reason, datetime.now()))
        conn.commit()
```

---

## Phase 7: Chantier 3 Integration (Observability)

### 7.1 LangSmith Tracing (Automatic)

```python
# LangSmith automatically traces all LangChain calls if:
# 1. LANGCHAIN_TRACING_V2=true
# 2. LANGCHAIN_API_KEY set
# 3. LANGCHAIN_PROJECT="Velmo-2.0"

# All calls are traced:
# - llm.invoke() → token count, latency
# - judge_agent.run() → tool calls, durations
# - vectorstore.similarity_search() → search time
# - RetrievalQA.run() → end-to-end latency
```

### 7.2 Custom Metrics

```python
def track_judge_metrics(extraction_id: str, facts_count: int, duration_ms: int):
    """Track judge quality metrics."""
    with psycopg2.connect(os.getenv("DATABASE_URL")) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO velmo.extraction_metadata
            (extraction_id, round_number, messages_analyzed, facts_created, duration_ms)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            str(extraction_id),
            1,  # round_number
            10,  # messages_analyzed
            facts_count,
            duration_ms
        ))
        conn.commit()
```

### 7.3 Cost Dashboard

```python
# Monitor in LangSmith:
# Project "Velmo-2.0" → Runs → Filter by model
# - Kimi 2.6 runs: track token usage
# - OpenAI embedding runs: track costs
# - Total cost per day/week/month

# CI/CD Gate Example:
# if judge_confidence_avg < 0.8:
#     fail deployment
```

---

## Phase 8: Testing & Validation

### 8.1 Unit Tests

```python
import pytest

def test_validate_input():
    """Test Pydantic validation."""
    assert validate_input("Hello world") == True
    assert validate_input("") == False

def test_content_safety():
    """Test safety classifier."""
    assert check_content_safety("Hello") == True
    assert check_content_safety("hate speech here") == False

def test_rate_limit():
    """Test rate limiting."""
    redis_client.delete("rate_limit:test-user")
    assert check_rate_limit("test-user") == True
    for _ in range(100):
        check_rate_limit("test-user")
    assert check_rate_limit("test-user") == False

def test_judge_trigger():
    """Test judge extraction."""
    mem = VelmoMemory("test-user")
    for i in range(10):
        mem.add_message("user", f"Message {i}")
    # Judge should be triggered on 10th message
```

### 8.2 Integration Test

```python
def test_full_flow():
    """Test end-to-end: input → judge → LLM → output."""
    response = process_user_message(
        user_id="test-user",
        message="Hello, my contract is KX-4471"
    )
    assert response is not None
    assert len(response) > 0
```

---

## Checklist: Ready for Production

- [ ] PostgreSQL schema created (facts, audit, metadata tables)
- [ ] Pinecone index initialized
- [ ] Redis running
- [ ] LangSmith project created
- [ ] All .env variables set and verified
- [ ] Kimi 2.6 LLM responding
- [ ] OpenAI embedding working
- [ ] Judge agent extracting facts
- [ ] Memory window holding 30 messages
- [ ] Retriever finding relevant facts
- [ ] QA chain generating responses
- [ ] Input guardrails blocking unsafe content
- [ ] Output guardrails redacting PII
- [ ] Audit logging all actions
- [ ] LangSmith dashboard showing traces
- [ ] Unit tests passing
- [ ] Integration tests passing

---

## Next Steps

1. Execute Phase 1-7 in order
2. Run tests (Phase 8)
3. Deploy infrastructure
4. Monitor in LangSmith dashboard
5. Move to CODE implementation phase

See also:
- [00_STACK_GLOBALE.md](./00_STACK_GLOBALE.md)
- [01_ARCHITECTURE_OVERVIEW.md](./01_ARCHITECTURE_OVERVIEW.md)
- [chantier-1-memoire/](./chantier-1-memoire/)
