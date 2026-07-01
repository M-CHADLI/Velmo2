# Azure Kimi 2.6 Integration Guide

## Overview

Kimi 2.6 is accessed via Azure OpenAI API in **two contexts**:

1. **LLM Principal**: Generate responses to user messages
2. **Judge Agent**: Extract facts from conversations every 10 messages

Both use the same Azure endpoint and connection method.

---

## Azure Connection Setup

### 1. Environment Variables

```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://eagwu-0283-resource.services.ai.azure.com/
AZURE_OPENAI_DEPLOYMENT=kimi-2.6
AZURE_OPENAI_API_VERSION=2024-08-01-preview
```

### 2. Verify Endpoint

Test your endpoint:

```bash
curl -X POST "https://eagwu-0283-resource.services.ai.azure.com/openai/v1/chat/completions" \
  -H "api-key: $AZURE_OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kimi-2.6",
    "messages": [{"role": "user", "content": "Say hello"}]
  }'
```

Expected response: Chat completion with Kimi output.

---

## LangChain Setup (Recommended)

### Using AzureChatOpenAI

```python
import os
from langchain.chat_models import AzureChatOpenAI

# Initialize LLM
llm = AzureChatOpenAI(
    deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),  # "kimi-2.6"
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),  # "https://eagwu-0283-resource..."
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),  # "2024-08-01-preview"
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0.7,
    max_tokens=2048,
    verbose=True
)

# Test it
response = llm.invoke("Say hello!")
print(response.content)
```

### Using Azure SDK Directly (Alternative)

```python
from azure.ai.openai import AzureOpenAI
from azure.identity import DefaultAzureCredential

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

response = client.chat.completions.create(
    model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    messages=[
        {"role": "user", "content": "Say hello!"}
    ]
)

print(response.choices[0].message.content)
```

---

## Context 1: LLM Principal (Responses)

### Standard LLM Call

```python
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks import LangSmithTracer

# Prompt template
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI support agent."),
    ("user", "{question}")
])

# Create chain
chain = prompt | llm

# Call with context
response = chain.invoke(
    {
        "question": f"Based on: {context}\n\nUser: {user_message}"
    },
    config={
        "callbacks": [LangSmithTracer(project_name="Velmo-2.0")]
    }
)

print(response.content)
```

### With Memory Context Injection

```python
# Get similar facts from Pinecone
similar_facts = vectorstore.similarity_search(user_message, k=5)

# Build context string
fact_context = "\n".join([
    f"- {fact.metadata.get('key', 'unknown')}: {fact.page_content}"
    for fact in similar_facts
])

# Include in prompt
full_prompt = f"""
You are a helpful support agent. Use the following facts about the user:

{fact_context}

User question: {user_message}

Respond concisely and helpfully.
"""

response = llm.invoke(full_prompt)
```

### Token Usage Tracking

```python
# LangSmith automatically tracks:
# - Input tokens
# - Output tokens
# - Total cost
# - Latency

# You can also access manually:
response = llm.invoke(prompt)

# In LangSmith dashboard:
# Project "Velmo-2.0" → Runs → Filter by "Kimi" model
# See token counts per run
```

---

## Context 2: Judge Agent (Fact Extraction)

### Judge Extraction Prompt

```python
from datetime import datetime

def create_judge_prompt(messages_list: list[dict]) -> str:
    """Create prompt for judge to extract facts."""
    
    messages_text = "\n".join([
        f"[{i+1}] {m['role'].upper()}: {m['content']}"
        for i, m in enumerate(messages_list[-10:])  # Last 10 msgs
    ])
    
    return f"""
You are a fact extraction agent. Analyze the following conversation and extract key facts.

Messages:
{messages_text}

Extract structured facts as JSON. Only extract facts you are confident about (confidence >= 0.8).

JSON format:
{{
  "facts": [
    {{
      "key": "contract_id",
      "value": "KX-4471",
      "type": "identifier",
      "confidence": 0.95,
      "source": "user_statement"
    }},
    {{
      "key": "customer_name",
      "value": "Karim",
      "type": "identifier",
      "confidence": 0.99,
      "source": "user_statement"
    }}
  ]
}}

Output ONLY valid JSON, no extra text.
"""

# Call judge
judge_prompt = create_judge_prompt(message_history)
judge_response = llm.invoke(judge_prompt)

# Parse JSON
import json
try:
    facts = json.loads(judge_response.content)
except json.JSONDecodeError:
    print("Judge response was not valid JSON")
    facts = {"facts": []}
```

### Judge Agent with Tools

```python
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.memory import ConversationBufferWindowMemory

def extract_facts_from_messages(messages_json: str) -> str:
    """Tool: Extract facts."""
    messages = json.loads(messages_json)
    prompt = create_judge_prompt(messages)
    response = llm.invoke(prompt)
    return response.content

def embed_facts(facts_json: str) -> str:
    """Tool: Embed facts."""
    facts = json.loads(facts_json)
    embeddings_response = []
    for fact in facts.get("facts", []):
        embedding = embeddings.embed_query(f"{fact['key']}: {fact['value']}")
        embeddings_response.append({
            "key": fact["key"],
            "embedding_dim": len(embedding)
        })
    return json.dumps(embeddings_response)

def persist_facts(facts_json: str) -> str:
    """Tool: Save facts to database."""
    # Implementation in Chantier 1 full spec
    return json.dumps({"status": "persisted"})

# Create agent
tools = [
    Tool(name="ExtractFacts", func=extract_facts_from_messages),
    Tool(name="EmbedFacts", func=embed_facts),
    Tool(name="PersistFacts", func=persist_facts)
]

judge_agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True
)

# Trigger every 10 messages
if message_count % 10 == 0:
    result = judge_agent.run(
        f"Extract and persist facts from messages: {json.dumps(messages_history[-10:])}"
    )
```

---

## Token Management

### Estimate Token Usage

```python
from langchain.callbacks import get_openai_callback

with get_openai_callback() as cb:
    response = llm.invoke("Extract facts from...")
    
    print(f"Prompt tokens: {cb.prompt_tokens}")
    print(f"Completion tokens: {cb.completion_tokens}")
    print(f"Total tokens: {cb.total_tokens}")
    print(f"Cost: ${cb.total_cost}")
```

### Per-Turn Token Budget

```
Turn #1-9 (No judge):
  - Input: ~200 tokens (message + context)
  - Output: ~150 tokens (response)
  - Total: ~350 tokens
  - Cost: ~$0.0001

Turn #10 (Judge trigger):
  - Judge input: ~2000 tokens (10 msgs + history)
  - Judge output: ~300 tokens (JSON facts)
  - LLM input: ~200 tokens (message + facts + context)
  - LLM output: ~150 tokens (response)
  - Total: ~2650 tokens
  - Cost: ~$0.00080

30-turn session cost:
  = (9 × 350) + (1 × 2650)
  = 3150 + 2650
  = ~5800 tokens total
  ≈ $0.0018 per session
```

### Cost Optimization

1. **Reduce judge cadence**: Every 15 msgs instead of 10
   - Cost ↓ 33%
   - Tradeoff: Fewer facts extracted

2. **Selective embedding**: Only embed facts with confidence > 0.9
   - Cost ↓ 20%
   - Tradeoff: Fewer facts searchable

3. **Smaller context window**: Embed only last 5 msgs for judge
   - Cost ↓ 30%
   - Tradeoff: Judge sees less context

---

## Error Handling

### Invalid JSON from Judge

```python
def safe_extract_facts(messages_text: str) -> dict:
    """Safely extract facts with fallback."""
    try:
        response = llm.invoke(create_judge_prompt(messages_text))
        facts = json.loads(response.content)
        return facts
    except json.JSONDecodeError:
        print("⚠️ Judge returned invalid JSON, retrying...")
        # Retry once
        response = llm.invoke(create_judge_prompt(messages_text))
        try:
            facts = json.loads(response.content)
            return facts
        except:
            print("❌ Judge failed, returning empty facts")
            return {"facts": []}
```

### Rate Limiting (Azure)

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor ** attempt
                        print(f"Retry in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        raise
        return wrapper
    return decorator

@retry_with_backoff()
def call_llm_safe(prompt: str):
    return llm.invoke(prompt)
```

---

## Monitoring in LangSmith

All Kimi calls are automatically traced if you use:

```python
from langchain.callbacks import LangSmithTracer

callbacks = [LangSmithTracer(project_name="Velmo-2.0")]

response = llm.invoke(prompt, config={"callbacks": callbacks})
```

In LangSmith Dashboard:
- Filter by "Deployment: kimi-2.6"
- See token counts per run
- See latency distribution
- See error rates
- Compare costs over time

---

## Testing Kimi Integration

### Unit Test

```python
import pytest

def test_llm_initialization():
    """Test Kimi is accessible."""
    assert llm is not None
    response = llm.invoke("Say hello")
    assert response.content is not None

def test_judge_extraction():
    """Test judge can extract facts."""
    messages = [
        {"role": "user", "content": "My name is Karim and contract is KX-4471"},
    ]
    prompt = create_judge_prompt(messages)
    response = llm.invoke(prompt)
    facts = json.loads(response.content)
    assert len(facts.get("facts", [])) > 0

def test_token_estimation():
    """Test token counting."""
    with get_openai_callback() as cb:
        llm.invoke("Test prompt")
        assert cb.total_tokens > 0
```

### Integration Test

```python
def test_full_judge_flow():
    """Test judge: extract → embed → persist."""
    messages = [
        {"role": "user", "content": "I am Karim"},
        {"role": "assistant", "content": "Hi Karim"},
    ] * 5  # 10 messages
    
    # Extract
    prompt = create_judge_prompt(messages)
    facts = json.loads(llm.invoke(prompt).content)
    assert len(facts["facts"]) > 0
    
    # Embed (would call OpenAI in real scenario)
    embeddings = [embeddings.embed_query(f.get("value")) for f in facts["facts"]]
    assert all(len(e) == 3072 for e in embeddings)
    
    # Persist (mock)
    result = persist_facts(json.dumps(facts))
    assert "status" in json.loads(result)
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid API key | Check `AZURE_OPENAI_API_KEY` in .env |
| 404 Not Found | Wrong endpoint | Verify `AZURE_OPENAI_ENDPOINT` format |
| 400 Bad Request | Wrong deployment | Confirm `AZURE_OPENAI_DEPLOYMENT=kimi-2.6` |
| Slow responses | Rate limited | Implement exponential backoff |
| Invalid JSON | Judge hallucination | Add validation, retry, use fallback |

---

## See Also

- [02_SCHEMAS.md](./02_SCHEMAS.md) — Fact schema for extraction
- [LANGSMITH_INTEGRATION.md](./LANGSMITH_INTEGRATION.md) — Tracing setup
- [../02_INTEGRATION_PLAN.md](../02_INTEGRATION_PLAN.md) — Full setup guide
