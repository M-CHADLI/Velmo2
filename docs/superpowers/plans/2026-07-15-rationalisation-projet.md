# Rationalisation Velmo2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer Velmo2 en projet mature : racine nettoyée, `src/` layout standard avec package unique `velmo`, config centralisée, bugs connus corrigés, CI GitHub Actions verte.

**Architecture:** Migration mécanique des 5 packages racine (`agent`, `memory`, `guardrails`, `business`, `observability`) vers `src/velmo/`, la config (`memory/config.py`) remontant en `velmo/config.py`. L'UI Streamlit part dans `apps/streamlit/`, les scripts éparpillés dans `scripts/`. Installation editable via uv rend `velmo` importable partout (fin des hacks `sys.path`).

**Tech Stack:** Python 3.11+, uv, setuptools (src layout), pytest + pytest-asyncio, ruff, GitHub Actions, PostgreSQL+pgvector (container `pgvector/pgvector:pg16` en CI).

## Global Constraints

- **Aucun changement de comportement fonctionnel** (mémoire, guardrails, tools, UI, CLI identiques)
- **Pas de renommage** de fonctions/classes publiques — seuls les chemins d'import changent
- Package unique : `velmo` sous `src/`, imports `from velmo.<module> import …`
- **uv exclusivement** (jamais pip), `UV_LINK_MODE=copy` (contrainte OneDrive)
- Suite de tests **100 % verte** à la fin (y compris les 2 tests streamlit actuellement en échec)
- Commits atomiques, messages **sans signature Co-Authored-By**
- `mehdi-superpowers/` est **déplacé** hors du repo (répertoire frère), jamais supprimé
- Déplacements de fichiers suivis par git via `git mv` (préserve l'historique)

---

## File Structure (cible)

```
Velmo2/
├── src/velmo/{__init__.py, config.py, agent/, memory/, guardrails/, business/, observability/}
├── apps/streamlit/{app_streamlit.py, components/, utils/}
├── scripts/{reset_db.py, seed_business_db.py, check_db.py, eval_memory.py, eval_guardrails.py, velmo_cli.py}
├── tests/  eval/  docs/{archive/, OPTIMISATIONS_LATENCE.md, superpowers/}
├── .github/workflows/ci.yml
├── README.md  Makefile  docker-compose.yml  pyproject.toml  .env.example  .gitignore
```

---

### Task 1: Nettoyage racine — suppressions, déplacement mehdi-superpowers, archivage docs

**Files:**
- Delete: `_/`, `__pycache__/`, `.pytest_cache/`, `velmo2.egg-info/`, `SKILL.md`, `skills-lock.json`
- Move (hors repo): `mehdi-superpowers/` → `../mehdi-superpowers/`
- Move (git mv): `chantier-1-memoire/`, `chantier-2-guardrails/`, `chantier-3-observabilite/`, `DEBRIEF_COMPLET.md`, `SCHEMA_FLUX_COMPLET.md`, `INDEX_CHANTIERS.md`, `00_STACK_GLOBALE.md`, `brief-phase2-creation-velmo2.md`, `brief-phase2-creation-velmo2.pdf` → `docs/archive/`
- Modify: `.gitignore`

**Interfaces:**
- Produces: racine propre ; `docs/archive/` ; `.gitignore` couvrant les artefacts

- [ ] **Step 1: Déplacer mehdi-superpowers hors du repo** (repo git indépendant — PAS `git mv`, PAS de suppression)

```bash
cd "C:\Users\mr mehdi\OneDrive\AI ENGINEER\Repository\Velmo2"
mv mehdi-superpowers "../mehdi-superpowers"
ls "../mehdi-superpowers/.claude-plugin/plugin.json"   # doit exister
```

- [ ] **Step 2: Supprimer les artefacts et résidus**

```bash
rm -rf _/ __pycache__/ .pytest_cache/ velmo2.egg-info/
git rm -f SKILL.md skills-lock.json 2>/dev/null || rm -f SKILL.md skills-lock.json
```

(`SKILL.md` et `skills-lock.json` : si non trackés, simple `rm`.)

- [ ] **Step 3: Compléter `.gitignore`**

Remplacer le contenu de `.gitignore` par :

```gitignore
# Secrets
.env
*.env
!.env.example

# Python artifacts
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.ruff_cache/
.venv/

# Superpowers scratch
.superpowers/
```

- [ ] **Step 4: Archiver les docs historiques**

```bash
mkdir -p docs/archive
git mv chantier-1-memoire chantier-2-guardrails chantier-3-observabilite docs/archive/
git mv DEBRIEF_COMPLET.md SCHEMA_FLUX_COMPLET.md INDEX_CHANTIERS.md 00_STACK_GLOBALE.md docs/archive/
git mv brief-phase2-creation-velmo2.md brief-phase2-creation-velmo2.pdf docs/archive/
```

- [ ] **Step 5: Vérifier**

```bash
git status --short   # que des R (renames) et D attendus, pas de fichier perdu
ls                    # racine : plus de chantier-*, DEBRIEF, brief-*, SKILL.md, _
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: clean root - archive legacy docs, remove artifacts, move plugin repo out"
```

---

### Task 2: Regrouper les scripts éparpillés dans `scripts/`

**Files:**
- Move (git mv): `check_db.py`, `eval_memory.py`, `eval_guardrails.py`, `velmo_cli.py` → `scripts/`
- Modify: `Makefile` (cibles `eval-memory`, `eval-guardrails`)

**Interfaces:**
- Consumes: racine nettoyée (Task 1)
- Produces: tous les scripts sous `scripts/` ; Makefile à jour

- [ ] **Step 1: Déplacer les scripts**

```bash
git mv check_db.py eval_memory.py eval_guardrails.py velmo_cli.py scripts/
```

- [ ] **Step 2: Mettre à jour le Makefile**

Dans `Makefile`, remplacer :

```makefile
eval-memory:
	@echo "$(GREEN)Running memory evaluation...$(NC)"
	python eval_memory.py

eval-guardrails:
	@echo "$(GREEN)Running guardrails evaluation...$(NC)"
	python eval_guardrails.py
```

par :

```makefile
eval-memory:
	@echo "$(GREEN)Running memory evaluation...$(NC)"
	uv run python scripts/eval_memory.py

eval-guardrails:
	@echo "$(GREEN)Running guardrails evaluation...$(NC)"
	uv run python scripts/eval_guardrails.py
```

- [ ] **Step 3: Vérifier que rien d'autre ne référence les anciens chemins**

```bash
grep -rn "eval_memory\.py\|eval_guardrails\.py\|check_db\.py\|velmo_cli\.py" --include="*.md" --include="Makefile" --include="*.py" . | grep -v scripts/ | grep -v docs/
```

Expected: aucune sortie (ou uniquement docs/archive, à ignorer).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: gather stray root scripts into scripts/"
```

---

### Task 3: Migration `src/` layout + config centralisée + réécriture des imports

**Files:**
- Move (git mv): `agent/`, `memory/`, `guardrails/`, `business/`, `observability/` → `src/velmo/` ; `memory/config.py` → `src/velmo/config.py`
- Create: `src/velmo/__init__.py`
- Modify: `pyproject.toml`, `src/velmo/memory/__init__.py`, tous les fichiers important les anciens noms (~30), `tests/conftest.py`, `Makefile` (db-init)

**Interfaces:**
- Produces: package `velmo` importable (`from velmo.config import load_settings, Settings, settings` ; `from velmo.memory import get_db, VelmoMemoryManager, MemoryManager` ; `from velmo.guardrails import GuardrailManager` ; `from velmo.agent.agent import VelmoAgent` ; `from velmo.business.tools import TOOLS` ; `from velmo.observability import trace_run`)

- [ ] **Step 1: Déplacer les packages**

```bash
mkdir -p src/velmo
git mv agent memory guardrails business observability src/velmo/
git mv src/velmo/memory/config.py src/velmo/config.py
```

- [ ] **Step 2: Créer `src/velmo/__init__.py`**

```python
"""Velmo 2.0 — Agent de support client IA (mémoire, guardrails, observabilité)."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Retirer la ré-exportation de config de `src/velmo/memory/__init__.py`**

Supprimer la ligne `from .config import Settings, load_settings` et retirer `"Settings", "load_settings",` de `__all__`. Le reste du fichier est inchangé.

- [ ] **Step 4: Réécrire tous les imports**

```bash
cd "C:\Users\mr mehdi\OneDrive\AI ENGINEER\Repository\Velmo2"
grep -rl --include="*.py" -E "^(from|import) (agent|memory|guardrails|business|observability)[. ]" src tests scripts streamlit | while read f; do
  sed -i -E \
    -e 's/^from memory\.config import/from velmo.config import/' \
    -e 's/^from (agent|memory|guardrails|business|observability)([. ])/from velmo.\1\2/' \
    -e 's/^import (agent|memory|guardrails|business|observability)([. ]|$)/import velmo.\1\2/' \
    "$f"
done
```

Puis corrections manuelles des cas particuliers :
- `src/velmo/*/…` : les imports internes relatifs (`from . import repository`) ne changent pas ; seuls les imports **absolus** inter-modules changent (ex. `agent/agent.py` : `from velmo.guardrails import GuardrailManager`, `from velmo.memory import MemoryManager`, `from velmo.config import settings as default_settings`, `from velmo.observability import set_user_context, trace_run`, `from velmo.business.tools import TOOLS, set_business_identity, get_discovered_email`, `from velmo.agent.schema import VelmoResponse`).
- `guardrails/classifier.py` : `from velmo.config import load_settings`.
- `guardrails/audit.py` : `from velmo.memory.database import get_db`.
- `scripts/seed_business_db.py` : import interne `from memory.database import get_db` (dans `insert_dataset`) → `from velmo.memory.database import get_db` ; `from memory.config import load_settings` → `from velmo.config import load_settings`.
- `tests/test_business_tools.py` : `import business.tools as t` → `import velmo.business.tools as t` (vérifier que sed l'a bien fait).
- `streamlit/app_streamlit.py` : `from memory import load_settings, get_db, VelmoMemoryManager` → `from velmo.config import load_settings` + `from velmo.memory import get_db, VelmoMemoryManager` (deux lignes).

Vérification qu'aucun ancien import ne subsiste :

```bash
grep -rn --include="*.py" -E "^(from|import) (agent|memory|guardrails|business|observability)[. ]" src tests scripts streamlit
```

Expected: aucune sortie.

- [ ] **Step 5: Mettre à jour `pyproject.toml`**

Remplacer la section packages :

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["velmo*"]
```

- [ ] **Step 6: Simplifier `tests/conftest.py`**

Le hack `sys.path` devient inutile (install editable). Nouveau contenu :

```python
# Le package velmo est installé en editable (uv sync) — pas de hack sys.path.
```

- [ ] **Step 7: Mettre à jour la cible `db-init` du Makefile**

```makefile
db-init:
	@echo "$(GREEN)Initializing database schema...$(NC)"
	uv run python -c "from velmo.memory import get_db; db = get_db(); db.init_db(); print('OK Database initialized')"
```

- [ ] **Step 8: Réinstaller et lancer la suite**

```bash
UV_LINK_MODE=copy uv sync
uv run pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: même bilan qu'avant migration (103 passed, 2 failed streamlit-asyncio — réparés en Task 5). Aucune erreur d'import.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: migrate to src/ layout with unified velmo package, centralize config"
```

---

### Task 4: Déplacer l'UI dans `apps/streamlit/` et supprimer les hacks sys.path

**Files:**
- Move (git mv): `streamlit/` → `apps/streamlit/`
- Modify: `apps/streamlit/app_streamlit.py:4-10`, `Makefile` (cible streamlit)

**Interfaces:**
- Consumes: package `velmo` installé (Task 3)
- Produces: `uv run streamlit run apps/streamlit/app_streamlit.py` fonctionnel

- [ ] **Step 1: Déplacer**

```bash
git mv streamlit apps/streamlit 2>/dev/null || { mkdir -p apps && git mv streamlit apps/streamlit; }
```

- [ ] **Step 2: Nettoyer les hacks sys.path de `apps/streamlit/app_streamlit.py`**

Remplacer :

```python
import streamlit as st
import sys
import logging
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
```

par :

```python
import streamlit as st
import sys
import logging
import asyncio
from pathlib import Path

# Composants locaux de l'app (components/, utils/) — le package velmo, lui,
# est installé en editable et n'a besoin d'aucun hack.
sys.path.insert(0, str(Path(__file__).parent))
```

(Le hack vers la racine disparaît ; celui vers le dossier de l'app reste car `components/` et `utils/` sont des modules locaux de l'app, pas du package.)

- [ ] **Step 3: Mettre à jour le Makefile**

```makefile
streamlit:
	@echo "$(GREEN)Starting Streamlit chat app...$(NC)"
	@echo "$(YELLOW)Opening browser at http://localhost:8501$(NC)"
	uv run streamlit run apps/streamlit/app_streamlit.py
```

- [ ] **Step 4: Vérifier le démarrage**

```bash
UV_LINK_MODE=copy uv run streamlit run apps/streamlit/app_streamlit.py --server.headless true &
sleep 12 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
```

Expected: `200`. Puis arrêter le process streamlit.

- [ ] **Step 5: Lancer les tests streamlit existants**

```bash
uv run pytest tests/ -k "streamlit" -v --tb=short
```

Expected: même état qu'avant (les 2 échecs asyncio persistent jusqu'à Task 5, pas de nouvelle erreur d'import).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: move Streamlit UI to apps/streamlit, drop root sys.path hack"
```

---

### Task 5: Corrections de code + suite 100 % verte

**Files:**
- Modify: `src/velmo/agent/agent.py:13,74`, `src/velmo/business/tools.py:22-23,70`, `scripts/seed_business_db.py:40-46`, `pyproject.toml` (dev deps)
- Test: `tests/test_agent_tool_loop.py`

**Interfaces:**
- Consumes: layout final (Tasks 3-4)
- Produces: `FALLBACK_MESSAGE` (constante module `velmo.agent.agent`) ; helper `_remember_email(email: str) -> None` dans `velmo.business.tools` ; suite pytest 100 % verte

- [ ] **Step 1: Écrire le test du message de repli (failing)**

Dans `tests/test_agent_tool_loop.py`, ajouter :

```python
from velmo.agent.agent import FALLBACK_MESSAGE


def test_tool_loop_exhaustion_returns_fallback_message(agent_with_looping_tool):
    """Si MAX_TOOL_ITERS est épuisé avec des tool_calls encore présents,
    la réponse ne doit jamais être vide."""
    response = agent_with_looping_tool.process_message("CLI-000001", "boucle")
    assert response.message == FALLBACK_MESSAGE
    assert response.message != ""
```

Note implémenteur : `agent_with_looping_tool` est une fixture à créer dans ce même fichier, sur le modèle des mocks existants du fichier (LLM mocké dont chaque réponse contient toujours `tool_calls` non vides et `content=""`, de sorte que la boucle épuise `MAX_TOOL_ITERS`). Reprendre le style de mock déjà utilisé dans `tests/test_agent_tool_loop.py`.

- [ ] **Step 2: Vérifier l'échec**

```bash
uv run pytest tests/test_agent_tool_loop.py -v --tb=short
```

Expected: FAIL (`ImportError: cannot import name 'FALLBACK_MESSAGE'`).

- [ ] **Step 3: Implémenter le repli dans `src/velmo/agent/agent.py`**

Après `MAX_TOOL_ITERS = 3` (ligne 13), ajouter :

```python
FALLBACK_MESSAGE = (
    "Je n'ai pas pu terminer le traitement de votre demande. "
    "Pouvez-vous reformuler ou préciser ?"
)
```

Et remplacer la ligne de retour de la boucle d'outils :

```python
        return ai.content if ai is not None and hasattr(ai, "content") else ""
```

par :

```python
        content = ai.content if ai is not None and hasattr(ai, "content") else ""
        return content if content else FALLBACK_MESSAGE
```

- [ ] **Step 4: Vérifier que le test passe**

```bash
uv run pytest tests/test_agent_tool_loop.py -v --tb=short
```

Expected: PASS (tous les tests du fichier).

- [ ] **Step 5: Helper identité dans `src/velmo/business/tools.py`**

Après `get_discovered_email()` (ligne 23), ajouter :

```python
def _remember_email(email: str) -> None:
    """Mémorise l'email découvert pendant la requête (voir note _identity)."""
    _identity["email"] = email
```

Et dans `get_customer_orders` (ligne 70), remplacer `_identity["email"] = email` par `_remember_email(email)`.

- [ ] **Step 6: Robustesse seed — `scripts/seed_business_db.py`**

Dans `generate_pools`, déplacer le chargement des settings dans le try :

```python
def generate_pools(settings=None) -> Pools:
    """Un appel LLM pour des pools riches ; fallback statique sur échec."""
    try:
        if settings is None:
            from velmo.config import load_settings
            settings = load_settings()
        llm = _build_llm(settings)
```

(le reste de la fonction est inchangé — le `except` existant couvre désormais aussi `load_settings()`).

- [ ] **Step 7: Ajouter pytest-asyncio et verdir la suite**

Dans `pyproject.toml` :

```toml
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "ruff>=0.2.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Puis :

```bash
UV_LINK_MODE=copy uv sync
uv run pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: **0 failed** (~106 passed). Si les 2 tests streamlit échouent encore, lire leur erreur : avec `asyncio_mode = "auto"` les `async def test_…` sont collectés nativement ; ajuster uniquement la config pytest, pas les tests.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "fix: tool-loop fallback message, identity helper, seed robustness, green test suite"
```

---

### Task 6: CI GitHub Actions + config ruff

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` (section `[tool.ruff]`)

**Interfaces:**
- Consumes: suite verte (Task 5)
- Produces: workflow CI (lint + tests avec PostgreSQL/pgvector)

- [ ] **Step 1: Config ruff dans `pyproject.toml`**

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests", "scripts"]

[tool.ruff.lint]
select = ["E", "W", "F"]
ignore = ["E501"]
```

- [ ] **Step 2: Vérifier le lint en local**

```bash
uv run ruff check .
```

Expected: aucune erreur. S'il y a des findings (imports morts, etc.), les corriger — ce sont précisément les résidus de vibe coding visés.

- [ ] **Step 3: Créer `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: velmo
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/velmo
      REDIS_URL: redis://localhost:6379/0
      AZURE_OPENAI_API_KEY: ci-dummy-key
      AZURE_OPENAI_ENDPOINT: https://ci-dummy.openai.azure.com/openai/v1
      AZURE_OPENAI_DEPLOYMENT_NAME: ci-dummy
      AZURE_OPENAI_API_VERSION: "2025-08-07"
      LANGSMITH_TRACING: "false"
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync
      - name: Lint
        run: uv run ruff check .
      - name: Tests
        run: uv run pytest tests/ -v --tb=short
```

- [ ] **Step 4: Vérifier localement que les tests passent avec des clés Azure factices**

```bash
AZURE_OPENAI_API_KEY=ci-dummy-key AZURE_OPENAI_ENDPOINT=https://ci-dummy.openai.azure.com/openai/v1 LANGSMITH_TRACING=false uv run pytest tests/ --tb=short -q 2>&1 | tail -3
```

Expected: 0 failed. Si un test fait un vrai appel réseau Azure, le marquer :

```python
@pytest.mark.integration
```

et exclure en CI en ajoutant `-m "not integration"` à la ligne Tests du workflow **et** dans `[tool.pytest.ini_options]` : `markers = ["integration: requires live services"]`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "ci: add GitHub Actions workflow (ruff + pytest with pgvector service)"
```

---

### Task 7: README réécrit + vérification finale

**Files:**
- Modify: `README.md` (réécriture complète), `Makefile` (cibles install/lint restantes)

**Interfaces:**
- Consumes: tout le layout final
- Produces: README honnête et exact ; `make help` cohérent

- [ ] **Step 1: Mettre à jour les cibles Makefile restantes**

```makefile
install:
	@echo "$(GREEN)Installing dependencies with uv...$(NC)"
	UV_LINK_MODE=copy uv sync

lint:
	@echo "$(GREEN)Running ruff linter...$(NC)"
	uv run ruff check .

format:
	@echo "$(GREEN)Formatting code with black...$(NC)"
	uv run black src tests scripts apps
	@echo "$(GREEN)Fixing lint issues with ruff...$(NC)"
	uv run ruff check . --fix

test:
	@echo "$(GREEN)Running tests...$(NC)"
	uv run pytest tests/ -v --tb=short
```

Supprimer la cible `requirements` (basée sur pip). Mettre à jour le texte de `make help` (`pip install -e .` → `uv sync`).

- [ ] **Step 2: Réécrire `README.md`**

Contenu complet :

````markdown
# Velmo 2.0 — Agent de support client IA

Agent d'assistance client avec mémoire persistante, guardrails de sécurité et interface Streamlit.
Projet d'exercice au niveau d'exigence « produit » : structure `src/` standard, tests, CI.

## Démarrage rapide

```bash
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2
make setup        # uv sync + docker-compose up + init DB
make streamlit    # http://localhost:8501
```

Prérequis : Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), Docker Desktop.

Configuration : copier `.env.example` vers `.env` et renseigner les clés (Azure OpenAI, LangSmith).

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
````

- [ ] **Step 3: Vérification finale complète**

```bash
uv run pytest tests/ --tb=short -q 2>&1 | tail -3     # 0 failed
uv run ruff check .                                     # clean
make db-init                                            # OK (Docker démarré)
uv run python scripts/velmo_cli.py --help 2>&1 | head -3 || uv run python -c "import scripts" 2>/dev/null; uv run python -c "from velmo.agent.agent import VelmoAgent; print('import OK')"
```

Expected: tests verts, lint clean, `import OK`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs: rewrite README for rationalized project structure"
```

---

## Self-Review

1. **Couverture spec :** §1 structure → Tasks 1-4 ; §2 config → Task 3 ; §3 corrections 1-4 → Task 5 ; §4 CI → Task 6 ; README/Makefile → Tasks 2,3,4,7 ; validation §5 → Steps de vérification de chaque task + Task 7 Step 3. ✅
2. **Placeholders :** aucun TBD/TODO ; le seul point conditionnel (marqueur `integration`, Task 6 Step 4) donne la procédure exacte. ✅
3. **Cohérence des noms :** `FALLBACK_MESSAGE`, `_remember_email`, `velmo.config.load_settings`, chemins `apps/streamlit/app_streamlit.py` cohérents entre tasks. ✅
