# Velmo 2.0 — Agent de support client IA

Agent d'assistance client avec mémoire persistante, guardrails de sécurité et interface Streamlit.
Projet d'exercice au niveau d'exigence « produit » : structure `src/` standard, tests, CI.

## Démarrage rapide

### Prérequis
- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (gestionnaire de dépendances)
- Docker Desktop (PostgreSQL + Redis)

### Installation et lancement (5 min)

```bash
# 1. Clone + cd
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2

# 2. Setup complet (install deps + BD + seed data)
make setup

# 3. Lancer l'interface Streamlit
make streamlit
# → http://localhost:8501
```

### Setup détaillé (étape par étape)

```bash
# 1. Lancer PostgreSQL + Redis en Docker
docker-compose up -d

# 2. Installer les dépendances
UV_LINK_MODE=copy uv sync

# 3. Initialiser la base de données
uv run python -c "from velmo.memory import get_db; db = get_db(); db.init_db()"

# 4. Seeder avec données fictives (1000 clients e-commerce)
uv run python scripts/seed_business_db.py

# 5. Vérifier les tests (doit afficher ~110 tests passing)
uv run pytest tests/ -v

# 6. Lancer Streamlit (UI web) — port 8501
make streamlit

# OU lancer le CLI (chat en terminal)
uv run python scripts/velmo_cli.py
```

### Configuration

Copier `.env.example` vers `.env` et renseigner les clés :
- `AZURE_OPENAI_API_KEY` — clé Azure OpenAI
- `AZURE_OPENAI_ENDPOINT` — endpoint Azure
- `AZURE_OPENAI_DEPLOYMENT_NAME` — nom du déploiement (ex: `gpt-5.4-mini`)
- `DATABASE_URL` — URL PostgreSQL (default: `postgresql://postgres:postgres@localhost:5432/velmo`)
- (optionnel) `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` pour observability

## Structure

```
src/velmo/          Package principal
├── config.py       Configuration centralisée (env vars)
├── agent/          Orchestration du chat (tool-calling)
├── memory/         Mémoire court terme (fenêtre glissante) + long terme (pgvector)
├── guardrails/     Garde-fous entrée/sortie (classifier LLM, PII, audit)
├── business/       Base e-commerce fictive + outils LangChain (démo)
└── observability/  Tracing LangSmith

apps/streamlit/     Interface web de chat
scripts/            Outils dev : seed DB, reset, éval, CLI
tests/              Suite pytest (~106 tests)
eval/               Datasets d'évaluation (.jsonl)
docs/               Documentation (archive/ = historique de conception)
```

## Commandes

```bash
make help         # liste complète
make test         # pytest
make lint         # ruff
make format       # black + ruff --fix
make db-init      # initialise le schéma PostgreSQL
uv run python scripts/seed_business_db.py   # seed la base fictive (50 clients)
uv run python scripts/velmo_cli.py          # chat en terminal
```

## Architecture

- **Mémoire** : fenêtre glissante 30 messages + extraction de facts (judge LLM toutes
  les 5 interactions) persistés dans PostgreSQL/pgvector.
- **Guardrails** : classifier LLM en entrée (fail-safe : bloque si le classifier échoue),
  redaction PII en sortie, audit trail en base.
- **Agent** : boucle tool-calling LangChain (3 itérations max, message de repli sinon)
  sur Azure OpenAI.
- **Base fictive** : 50 clients e-commerce générés (fixture de démo — remplacerait une
  vraie base client en production).

## CI

GitHub Actions à chaque push : `ruff check` + `pytest` contre un PostgreSQL/pgvector
en service container. Voir `.github/workflows/ci.yml`.

## Licence

MIT
