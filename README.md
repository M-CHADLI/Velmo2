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

## Canal SMS (Twilio)

En plus de Streamlit, Velmo2 expose un canal SMS via Twilio.

### Setup

1. Créer un compte [Twilio](https://www.twilio.com/), récupérer Account SID, Auth Token, et un numéro Twilio.
2. Renseigner dans `.env` : `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.
3. Lancer le serveur : `make sms-server` (http://localhost:8000).
4. En dev local, exposer publiquement avec [ngrok](https://ngrok.com/) : `ngrok http 8000`.
5. Dans la console Twilio, configurer le webhook du numéro SMS sur `https://<ngrok-url>/sms/webhook` (méthode POST).
6. Le lookup client se fait par numéro de téléphone (colonne `phone` de `customers`, générée en format E.164 par le seed).

En production, remplacer l'URL ngrok par l'URL stable du serveur déployé — aucun changement de code nécessaire.

## Boucle qualité (Chantier 3 — Évaluation & MLOps)

Pour prouver que l'agent ne régresse pas d'une version à l'autre, trois suites
d'évaluation rejouent des jeux de cas et produisent une **note globale sur 100** :

| Suite | Jeu de cas | Ce qu'elle mesure |
|---|---|---|
| Mémoire | `eval/memory_cases.jsonl` | L'agent se souvient-il (fil long, multi-session, oubli) ? |
| Garde-fous | `eval/guardrail_cases.jsonl` | % de cas bien traités + taux de blocage et de faux positifs |
| Qualité | `eval/quality_cases.jsonl` | L'agent répond-il correctement aux questions support courantes ? |

**Lancer l'évaluation complète :**

```bash
make quality          # = uv run python mlops/run_eval.py
```

Le script :
1. lance les 3 suites et calcule la note globale (pondération 40 % mémoire /
   40 % garde-fous / 20 % qualité, seuil de livraison à 70/100) ;
2. écrit un rapport lisible dans `mlops/report.md` (note globale, note par suite,
   taux de blocage, taux de faux positifs, latence moyenne, coût estimé) ;
3. ajoute une ligne horodatée à `mlops/scores/history.jsonl` (suivi de la note
   dans le temps) ;
4. **retourne un code d'erreur si la note passe sous le seuil** → c'est ce qui
   bloque la livraison.

> Un garde-fou retiré ou la mémoire désactivée font chuter la note sous le seuil :
> `make quality` échoue alors avec le code de sortie 1, empêchant la livraison.

## CI

- `.github/workflows/ci.yml` — à chaque push : `ruff check` + `pytest` contre un
  PostgreSQL/pgvector en service container. Rapide, gratuit (LLM mocké).
- `.github/workflows/quality.yml` — la boucle qualité ci-dessus. Déclenchée
  **manuellement** (onglet Actions → « Run workflow ») car elle appelle le vrai
  LLM Azure. Nécessite les secrets `AZURE_OPENAI_*` dans les réglages du repo.
  Bloque si la note globale est sous le seuil et publie `mlops/report.md` en artifact.

## Licence

MIT
