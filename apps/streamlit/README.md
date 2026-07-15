# Velmo Streamlit Chat Interface

Web chat interface to interact with Velmo customer support agent.

## Launch

From the repository root:

```bash
make streamlit
```

Or manually:

```bash
uv run streamlit run apps/streamlit/app_streamlit.py
```

Open http://localhost:8501

## Prerequisites

- Run `make setup` from the repository root to initialize:
  - `uv sync` — install all dependencies
  - Docker PostgreSQL and Redis services
  - Database initialization
- `.env` file must be configured (see `.env.example`)

## Project Structure

- `app_streamlit.py` — Application entry point
- `components/` — Reusable UI components
  - `chat_handler` — Chat message processing
  - `database_viewer` — Database query interface
- `utils/` — Utility modules
  - `session_manager` — Streamlit session state management

## Configuration

Set the following in `.env`:
- `DATABASE_URL` — PostgreSQL connection string
- `AZURE_OPENAI_API_KEY` — Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT` — Azure OpenAI endpoint
- `REDIS_URL` — Redis connection (optional, for caching)

See `.env.example` for complete configuration list.
