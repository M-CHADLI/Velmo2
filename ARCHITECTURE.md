# Architecture Velmo 2.0

## Vue d'ensemble

Velmo 2.0 est un agent d'assistance client IA avec mémoire persistante, garde-fous de sécurité et interface web. Le système orchestre trois couches : entrée sécurisée (guardrails), mémoire (court/long terme), et LLM (Azure OpenAI).

---

## Schéma de séquence — Flux d'une interaction utilisateur

```mermaid
sequenceDiagram
    participant User as 👤 Utilisateur
    participant UI as 💻 Streamlit UI
    participant Agent as 🤖 Agent
    participant Memory as 🧠 Mémoire
    participant LLM as ⚡ Azure LLM
    participant DB as 💾 PostgreSQL

    User->>UI: 1. Envoie message
    activate UI
    UI->>Agent: message + user_id
    activate Agent
    
    Agent->>Agent: 2. Input Guard (Classifier)<br/>Bloque haine/violence/injection
    Note over Agent: Fail-safe BLOCK<br/>si classifier échoue
    
    alt Blocked
        Agent-->>UI: Erreur sécurité
        UI-->>User: Message rejeté
    else Allowed
        Agent->>Memory: 3. Short-term memory<br/>Fenêtre 30 messages
        activate Memory
        
        Note over Memory: Toutes les 5 turns:<br/>Judge Agent extrait facts
        Memory->>DB: 4. Long-term memory<br/>pgvector embeddings
        activate DB
        
        Agent->>LLM: 5. Tool-calling loop<br/>(MAX 3 itérations)
        activate LLM
        
        loop Jusqu'à réponse ou MAX
            LLM-->>Agent: Réponse + tool_calls
            Agent->>Agent: Exécute outils<br/>(get_orders, lookup_order)
            Agent->>LLM: Résultat + continue
        end
        
        LLM-->>Agent: Réponse finale
        Note over Agent: Fallback message<br/>si boucle épuisée
        deactivate LLM
        
        Agent->>Agent: 6. Output Guard<br/>Redaction PII (emails, IBAN)
        
        Agent->>Memory: Update short-term
        Memory->>DB: Audit trail
        deactivate Memory
        deactivate DB
        
        Agent-->>UI: Réponse nettoyée + métadonnées
    end
    
    deactivate Agent
    UI-->>User: Affichage + indicateurs
    deactivate UI
```

---

## Structure du répertoire

```
Velmo2/
├── src/velmo/                          # 🎯 Package principal installable
│   ├── __init__.py                     # Métadonnées version + exports
│   ├── config.py                       # Settings + load_settings() — config centralisée
│   │
│   ├── agent/                          # 🤖 Orchestration LLM + tool-calling
│   │   ├── __init__.py
│   │   ├── agent.py                    # Agent class : input/output guards, tool loop (MAX_TOOL_ITERS=3)
│   │   └── schema.py                   # Pydantic schemas (Message, ToolCall, etc.)
│   │
│   ├── guardrails/                     # 🛡️ Sécurité : classification, redaction PII
│   │   ├── __init__.py
│   │   ├── classifier.py               # InputGuard : LLM classifier (fail-safe BLOCK)
│   │   ├── input_guard.py              # Valide message avant traitement
│   │   ├── output_guard.py             # Redact emails, IBAN, etc. en réponse
│   │   ├── manager.py                  # GuardrailsManager : orchestrate guards
│   │   ├── audit.py                    # Analyse + testing des guardrails
│   │   ├── rules.py                    # Règles de redaction (regex patterns)
│   │   └── schema.py                   # Enums + validation
│   │
│   ├── memory/                         # 🧠 Mémoire court + long terme
│   │   ├── __init__.py                 # Exports VelmoMemoryManager, DB helpers
│   │   ├── manager.py                  # VelmoMemoryManager : orchestrate tiers
│   │   ├── short_term.py               # Fenêtre glissante 30 messages
│   │   ├── long_term.py                # pgvector + embeddings OpenAI
│   │   ├── judge.py                    # Judge Agent : extraction facts (toutes 5 tours)
│   │   ├── database.py                 # Connection pools + async DB helpers
│   │   ├── schema.py                   # ORM-like Message, Fact, Embedding
│   │   └── [other files]               # Migration SQL, seed data
│   │
│   ├── business/                       # 💼 Outils métier + e-commerce fictif
│   │   ├── __init__.py
│   │   ├── tools.py                    # LangChain tools : get_orders, lookup_order, etc.
│   │   ├── repository.py               # Business DB queries (SELECT * FROM orders)
│   │   ├── generate.py                 # Génère 50 clients + commandes fictives
│   │   ├── models.py                   # SQLAlchemy ORM models
│   │   └── schema.py                   # Pydantic schemas (Order, Customer)
│   │
│   └── observability/                  # 📊 Tracing LangSmith (optional)
│       ├── __init__.py
│       └── tracing.py                  # configure_langsmith() pour debug/metrics
│
├── apps/
│   └── streamlit/                      # 🌐 UI web (Streamlit)
│       ├── README.md                   # Instructions déploiement Streamlit Cloud
│       ├── app_streamlit.py            # Point d'entrée : chat + DB viewer
│       ├── components/                 # Composants Streamlit réutilisables
│       └── utils/                      # Helpers (state management, formatting)
│
├── scripts/                            # 🔧 Scripts utilitaires
│   ├── velmo_cli.py                    # CLI : chat interactif (click-based)
│   ├── seed_business_db.py             # Init : génère 50 clients + seed data
│   ├── reset_db.py                     # Reset : DROP + CREATE schémas
│   ├── check_db.py                     # Health check : connexion + stats
│   └── eval_*.py                       # Evaluation guardrails, memory, quality
│
├── tests/                              # ✅ Suite de tests (pytest)
│   ├── conftest.py                     # Fixtures : mock LLM, DB, etc.
│   ├── test_agent_*.py                 # Agent orchestration + tool-loop
│   ├── test_guardrails_*.py            # Classifier, input/output guards
│   ├── test_memory_*.py                # Short/long-term, judge agent
│   ├── test_business_*.py              # Tools, repository, generation
│   ├── test_observability.py           # Tracing LangSmith
│   └── test_streamlit_*.py             # UI state + components
│
├── docs/                               # 📖 Documentation
│   ├── OPTIMISATIONS_LATENCE.md        # Tuning guide : timeout, batch size
│   ├── superpowers/
│   │   ├── specs/                      # Design docs (design approvals)
│   │   └── plans/                      # Implémentation plans (step-by-step)
│   └── archive/                        # 📦 Docs historiques (vibe coding)
│       ├── chantier-1-memoire/         # Phase 1 : architecture mémoire
│       ├── chantier-2-guardrails/      # Phase 2 : guardrails
│       ├── chantier-3-observabilite/   # Phase 3 : observability
│       ├── DEBRIEF_COMPLET.md          # Résumé global (final)
│       ├── SCHEMA_FLUX_COMPLET.md      # Diagrammes flux complets
│       └── ...
│
├── eval/                               # 📊 Datasets pour évaluation
│   ├── memory_cases.jsonl              # Test cases : memory + recall
│   ├── quality_cases.jsonl             # Test cases : réponse quality
│   └── guardrail_cases.jsonl           # Test cases : injection, toxicity
│
├── .github/
│   └── workflows/
│       └── ci.yml                      # GitHub Actions : pytest + ruff + pgvector
│
├── .env.example                        # Template variables env (DATABASE_URL, Azure keys)
├── .gitignore                          # Ignore __pycache__, .venv, .env, etc.
├── docker-compose.yml                  # PostgreSQL 16 + Redis (dev local)
├── pyproject.toml                      # uv config, setuptools, pytest, ruff
├── Makefile                            # Targets : setup, streamlit, test, lint
├── README.md                           # Vue d'ensemble + quick start
├── ARCHITECTURE.md                     # Ce fichier 📍
├── uv.lock                             # Lock file (uv sync, jamais pip)
└── velmo2.egg-info/                    # Metadata (regénéré par uv)
```

---

### Descriptions des modules clés

| Module | Rôle | Clé |
|--------|------|-----|
| **agent/** | Orchestration LLM + tool-calling loop | Cœur logique (agent.py 3 itérations max) |
| **guardrails/** | Input/output guards sécurité (classifier LLM fail-safe BLOCK) | Protège contre injection + redact PII |
| **memory/** | Mémoire court (30 msgs) + long (pgvector embeddings) | Contexte conversationnel + persistence BD |
| **business/** | E-commerce fictif (50 clients, outils query orders) | Données démo + LangChain tools |
| **observability/** | Tracing LangSmith (optional, off by default) | Debug + metrics LLM |
| **scripts/** | Utilitaires CLI (seed DB, health check, eval) | Setup + ops locale |
| **apps/streamlit/** | UI web avec dropdown client | Frontend démo |
| **tests/** | 106 tests (unit + integration + e2e) | CI verte + coverage |
| **docs/archive/** | Historique vibe coding (chantiers 1-3) | Référence design evolution |

---

## Choix architecturaux importants

### 1. **Package unique `velmo` sous `src/`**

**Choix :** Structure standard Python `src/` layout avec package unifié.

**Justification :**
- Isolation claire : code produit (src/) vs tests/docs
- Installation editable propre sans hacks `sys.path`
- Packaging et distribution futur simplifié
- Importable de n'importe où : `from velmo.config import load_settings`

**Impact :**
- Migration complète : `agent/`, `memory/`, `guardrails/`, `business/`, `observability/` → `src/velmo/`
- Config centralisée : `velmo/config.py` (était disséminée dans `memory/config.py`)
- Aucun changement de comportement fonctionnel

---

### 2. **Fail-Safe BLOCK sur classifier**

**Choix :** Si le classifier LLM échoue, bloquer TOUS les messages.

**Justification :**
- Sécurité par défaut : mieux trop restrictif que trop permissif
- Si la classification s'effondre, on ne peut pas faire confiance au filtrage
- Exception = condition exceptionnelle = arrêt défensif

**Impact :**
- Quand le classifier est down, aucun message ne passe (utilisateur voit "Service temporarily unavailable")
- Tests difficiles à maintenir : les mocks du classifier doivent être robustes
- Production critique : la disponibilité du classifier affecte la disponibilité de l'agent

**Mitigation :**
- Timeout court sur classifier (~2-3s)
- Fallback message clair signalant l'indisponibilité
- Monitoring des appels classifier (LangSmith)

---

### 3. **Mémoire court-terme (fenêtre glissante 30 messages)**

**Choix :** Limiter le contexte conversationnel à 30 messages récents.

**Justification :**
- Coût LLM : le contexte env. 10-15 tokens/message → 300-450 tokens par appel LLM
- Relevance : au-delà de 30 messages (~15-20 min), la contexte devient bruit
- Fenêtre glissante (pas FIFO strict) : garde les messages les plus récents

**Impact :**
- Contexte optimisé = coût et latence LLM réduits
- Perte de contexte sur conversation très longue (> 30 messages)
- Trade-off : bien calibré pour un chat support client (interactions courtes/moyennes)

---

### 4. **Judge Agent (extraction de facts toutes les 5 tours)**

**Choix :** Appeler le LLM de judge tous les 5 tours pour extraire des facts vers la mémoire longue.

**Justification :**
- Réduit les appels judge : coût LLM contrôlé (1 appel judge pour ~5 appels agent)
- Oubli sélectif : on ne stocke que les moments-clés (décisions, changements de sujet)
- Récupération sémantique : embeddings pgvector + cosine search retrouvent les facts pertinents

**Impact :**
- Facts fragmentés : si un client pose 20 questions, on en extrait ~4 (stratégie acceptable pour support)
- Risque d'oubli : un fait émis à tour 4, pas repris après → peut être oublié
- Scalabilité : base de facts croît lentement (1 fact/5 tours vs 1/tour)

---

### 5. **Boucle tool-calling limitée à 3 itérations**

**Choix :** MAX_TOOL_ITERS = 3 pour éviter les boucles infinies d'outils.

**Justification :**
- Runaway loops : certains LLM générèrent des appels outils infinies (ex. halluciner un outil qui n'existe pas)
- Latence : 3 aller-retours outils = ~6-9s (acceptable) ; 10+ = inacceptable
- Fallback message : si épuisé, répondre avec "Je n'ai pas pu terminer..." plutôt que ""

**Impact :**
- Req complexes bloquées : "Donne-moi le détail de mes 50 dernières commandes" → le LLM peut s'arrêter après 3 appels
- Behavior dégradé acceptable : client reçoit une réponse incomplète mais honnête ("n'a pas pu terminer")
- Tests difficiles : fixture pour générer des outils infinis est complexe

---

### 6. **Mémoire longue : pgvector + embeddings OpenAI**

**Choix :** Stocker les facts avec embeddings dans PostgreSQL + pgvector pour recherche sémantique.

**Justification :**
- Recherche sémantique : `SELECT * FROM facts ORDER BY embedding <=> query_embedding LIMIT 5` retrouve les facts proches
- Persistance : base de données durable, indépendante du cycle de la session
- Scalabilité : pgvector est efficace jusqu'à des millions de facts

**Impact :**
- Coût : 1 embedding/fact + stockage pgvector
- Latence : requête cosine search ~1-2ms sur des millions de facts
- Qualité : embeddings OpenAI sont de haute qualité, mais changement de modèle embedding = re-embedding massif

---

### 7. **UI Streamlit + sélecteur de client manuel**

**Choix :** UI web Streamlit avec dropdown pour choisir un client (fixture de démo).

**Justification :**
- Démo simple : pas d'auth compliquée, test immédiat sur n'importe quel client
- Développement : itération rapide sans mock d'authentification
- **Production :** remplacer par vrai système d'auth (OAuth, JWT) + client implicite

**Impact :**
- Sécurité dev : acceptable (fixture de test, démo uniquement)
- Sécurité prod : NON acceptable (client doit être implicite via auth)
- Tests : fixture `CLI-000001` toujours disponible pour reproductibilité

---

### 8. **CI GitHub Actions avec pgvector en container**

**Choix :** Service PostgreSQL+pgvector spun up par GitHub Actions lors de chaque CI.

**Justification :**
- Tests BD réalistes : mock d'une BD ne capture pas les bugs pgvector/SQL
- Isolation : service BD par run de CI, aucune pollution inter-runs
- Vitesse : image pgvector 500MB, spin-up ~10s (acceptable)

**Impact :**
- CI duration : +10-15s pour le spin-up, pas de re-provisioning manuel
- Flakiness : santé du service affecte tous les tests BD
- Extensibilité : facile d'ajouter d'autres services (Redis, etc.)

---

## Configuration globale

### Dépendances clés

| Module | Rôle | Version | Notes |
|--------|------|---------|-------|
| **LangChain** | Orchestration LLM + tools | 0.1+ | Chain abstracts prompting |
| **Pydantic** | Validation schémas | 2.6+ | Settings + schemas |
| **psycopg** | Driver PostgreSQL | 3.1+ | Binary + editable API |
| **Streamlit** | UI web | 1.28+ | State management `st.session_state` |
| **LangSmith** | Observability (optionnel) | 0.1+ | Tracing + metrics |
| **pytest-asyncio** | Tests async | 0.23+ | Async fixtures |
| **ruff** | Lint rapide | 0.2+ | All checks |

### Environnement

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/velmo

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://...openai.azure.com/openai/v1
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.4-mini
AZURE_OPENAI_API_VERSION=2025-08-07

# Guardrails
CLASSIFIER_DEPLOYMENT_NAME=gpt-5.4-mini
CLASSIFIER_MAX_TOKENS=16
RESPONSE_MAX_TOKENS=512

# Optional
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
```

---

## Tests

- **Suite :** 106 tests (unit + integration)
- **Coverage :** agent, memory, guardrails, business modules
- **Fixtures :** 50 clients e-commerce fictifs, mocks LLM, DB réelle en CI
- **CI :** GitHub Actions (ruff + pytest + pgvector service)

---

## Déploiement

### Local dev
```bash
make setup      # uv sync + Docker (PG + Redis) + init DB
make streamlit  # http://localhost:8501
```

### Streamlit Cloud (déploiement en production)
- Repo public GitHub → connecter à https://streamlit.io/cloud
- Secrets via UI Streamlit Cloud (DATABASE_URL, Azure keys)
- Redéploie auto à chaque push

### Future : Azure App Service / Railway
- Container Dockerfile fourni (image Python 3.11-slim + pip install)
- PostgreSQL Azure Flexible Server (Burstable tier)
- Redis Azure Cache (Basic tier)

---

## Limites connues

1. **Sélecteur client manuel** : production nécessite auth réelle
2. **Fallback tool-loop** : req complexes peuvent s'arrêter à 3 itérations
3. **Mémoire judge** : facts extraits toutes les 5 tours (not real-time)
4. **pgvector** : migration de modèle embedding demande re-embedding massif
5. **Fail-safe classifier** : downtime du classifier = downtime agent (critique)

---

## Améliorations futures (roadmap)

- [ ] Monitoring LangSmith complet (latency, cost, error rates)
- [ ] Multi-user support (sessions isolées par user)
- [ ] Persistent chat history (UI retention longue)
- [ ] Feedback loop (user rating → model fine-tuning signal)
- [ ] Rate limiting Redis (protéger contre abuse)
- [ ] Internationalization (support multilingue)

---

**Dernière mise à jour :** 2026-07-15 (après rationalisation `feat/streamlit-cloud-deploy`)
