# Velmo 2.0 Streamlit Chat Interface

Simple web chat interface to talk to Velmo support agent.

## Setup

```bash
# Install dependencies
pip install -e .

# Start Docker services
docker-compose up -d

# Initialize database
python -c "from memory import get_db; get_db().init_db()"

# Run Streamlit app
streamlit run streamlit/app_streamlit.py
```

Open http://localhost:8501

## Architecture

```
user input
  ↓
[input guardrails] - check for harmful/injection/secrets
  ↓
[memory] - record user message + retrieve context
  ↓
[LLM: Kimi 2.6] - generate response
  ↓
[output guardrails] - check for PII/compliance
  ↓
[memory] - record assistant response
  ↓
display to user
```

## Features

- ✅ Real-time chat with Velmo
- ✅ Full safety pipeline (input + output guardrails)
- ✅ Memory integration (facts extraction + retrieval)
- ✅ Message history in session
- ✅ Error handling + graceful fallbacks

## Configuration

Set in `.env`:
- `DATABASE_URL`: PostgreSQL connection
- `AZURE_OPENAI_API_KEY`: Kimi 2.6 key
- `AZURE_OPENAI_ENDPOINT`: Azure endpoint

See `.env.example` for full list.

## Troubleshooting

**"Database connection error":**
```bash
docker-compose up -d
```

**"Module not found":**
```bash
pip install -e .
```

**"Streamlit not found":**
```bash
pip install streamlit>=1.28.0
```
