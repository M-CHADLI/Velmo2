# Rationalisation du projet Velmo2 — Design

**Goal:** Transformer Velmo2 d'un projet "vibe codé" en projet mature : structure Python standard `src/` layout, racine nettoyée, config centralisée, corrections des bugs connus, CI GitHub Actions verte.

**Contexte:** Le projet fonctionne (agent IA + mémoire + guardrails + UI Streamlit, ~3 000 lignes Python) mais a accumulé des résidus : 6 gros documents Markdown à la racine, dossiers de design historiques (`chantier-1/2/3`), artefacts (`__pycache__`, `velmo2.egg-info`, `_/`), scripts éparpillés, un repo git indépendant (`mehdi-superpowers/`) imbriqué, et une config globale logée dans `memory/`.

**Décisions cadrantes (validées) :**
- Refonte complète (structure + hygiène de code + architecture) — pas seulement du rangement
- Niveau d'exigence "vrai produit", tout en restant un exercice : **aucun changement de périmètre fonctionnel** (base e-commerce fictive, sélecteur client, CLI, tracing LangSmith : tout reste tel quel)
- Outillage qualité : **CI GitHub Actions** (tests + lint) ; les 2 tests en échec sont réparés car la CI doit être verte

---

## Contraintes globales

- **Aucun changement de comportement fonctionnel** : mémoire, guardrails, tools, UI, CLI identiques
- **Pas de renommage** de fonctions/classes publiques — seuls les chemins d'import changent
- **Package unique** : `velmo` sous `src/`, imports `from velmo.<module> import …`
- **Environnement** : uv exclusivement (jamais pip), `UV_LINK_MODE=copy` (contrainte OneDrive)
- **Suite de tests** : 100 % verte à la fin (y compris les 2 tests streamlit actuellement en échec — dépendance `pytest-asyncio` manquante)
- **Commits atomiques** par étape, messages sans signature Co-Authored-By
- **`mehdi-superpowers/`** est déplacé hors du repo (ex. `~/OneDrive/AI ENGINEER/Repository/mehdi-superpowers`), jamais supprimé

---

## 1. Structure cible

```
Velmo2/
├── src/velmo/                  # Package unique installable
│   ├── __init__.py
│   ├── config.py               # ← memory/config.py (Settings + load_settings)
│   ├── agent/                  # ← agent/
│   ├── memory/                 # ← memory/ (sans config.py)
│   ├── guardrails/             # ← guardrails/
│   ├── business/               # ← business/
│   └── observability/          # ← observability/
├── apps/
│   └── streamlit/              # ← streamlit/ (app_streamlit.py, components/, utils/)
├── scripts/                    # reset_db.py, seed_business_db.py
│   ├── check_db.py             # ← racine
│   ├── eval_memory.py          # ← racine
│   ├── eval_guardrails.py      # ← racine
│   └── velmo_cli.py            # ← racine
├── tests/                      # inchangé (imports mis à jour)
├── eval/                       # datasets .jsonl (inchangé)
├── docs/
│   ├── archive/                # docs historiques du vibe coding
│   │   ├── chantier-1-memoire/
│   │   ├── chantier-2-guardrails/
│   │   ├── chantier-3-observabilite/
│   │   ├── DEBRIEF_COMPLET.md
│   │   ├── SCHEMA_FLUX_COMPLET.md
│   │   ├── INDEX_CHANTIERS.md
│   │   ├── 00_STACK_GLOBALE.md
│   │   ├── brief-phase2-creation-velmo2.md
│   │   └── brief-phase2-creation-velmo2.pdf
│   ├── OPTIMISATIONS_LATENCE.md
│   └── superpowers/            # specs + plans (inchangé)
├── .github/workflows/ci.yml    # NOUVEAU
├── README.md                   # réécrit : structure réelle, commandes uv, état honnête
├── Makefile                    # chemins mis à jour
├── docker-compose.yml          # inchangé
├── pyproject.toml              # réécrit pour src/ layout
├── .env.example                # inchangé
└── .gitignore                  # complété (egg-info, caches)
```

### Suppressions pures (pas d'archive)

| Élément | Raison |
|---|---|
| `_/` | dossier vide accidentel |
| `__pycache__/`, `.pytest_cache/`, `velmo2.egg-info/` | artefacts régénérables, ajoutés au `.gitignore` |
| `SKILL.md`, `skills-lock.json` | résidus d'expérimentation skills |

### Déplacement hors repo

- `mehdi-superpowers/` → répertoire frère du repo (c'est un repo git indépendant du plugin de skills ; il n'a rien à faire dans Velmo2)

---

## 2. Config centralisée

- `memory/config.py` devient `src/velmo/config.py` : la classe `Settings` configure LLM, guardrails, LangSmith et DB — elle n'est pas spécifique à la mémoire.
- Tous les consommateurs importent `from velmo.config import load_settings, Settings`.
- `memory/__init__.py` cesse de ré-exporter `load_settings`/`Settings` (une seule source d'import).

## 3. Corrections de code (issues connues des revues précédentes)

1. **`agent/agent.py`** — si `MAX_TOOL_ITERS` est épuisé avec des tool_calls encore présents, la réponse peut être `""` → message de repli explicite (ex. « Je n'ai pas pu terminer le traitement de votre demande, pouvez-vous reformuler ? »).
2. **`business/tools.py`** — accès direct `_identity["email"]` remplacé par le même helper que le reste du module (cohérence de style, comportement identique).
3. **`scripts/seed_business_db.py`** — l'appel `load_settings()` rejoint le try/except de `generate_pools` (robustesse si `Settings` gagne un champ requis).
4. **`pyproject.toml`** — groupe dev : ajout de `pytest-asyncio` (répare les 2 tests streamlit en échec) ; `[tool.setuptools.packages.find] where = ["src"]` ; config `ruff` minimale ; entrée console optionnelle pour le CLI.

## 4. CI GitHub Actions

`.github/workflows/ci.yml`, déclenché sur `push` et `pull_request` :

- **Job unique `test`** (ubuntu-latest) :
  - checkout + install uv (avec cache)
  - `uv sync`
  - Lint : `uv run ruff check .`
  - Service PostgreSQL+pgvector en container (`pgvector/pgvector:pg16`, credentials `postgres/postgres`, port 5432) pour les tests DB
  - Variables d'env factices pour Azure OpenAI (aucun vrai appel LLM en CI ; si des tests en font, ils sont marqués `@pytest.mark.integration` et exclus de la CI)
  - Tests : `uv run pytest tests/ -v`
- **Pas de déploiement** dans la CI (le déploiement Streamlit Cloud est un sujet séparé, déjà spécifié dans `2026-07-10-velmo2-streamlit-cloud-deployment-design.md`).

## 5. Validation (preuve de non-régression)

1. `uv run pytest tests/` → 100 % vert en local (~105 tests, dont les 2 réparés)
2. `uv run streamlit run apps/streamlit/app_streamlit.py` → app démarre, chat fonctionnel avec un client sélectionné, DB viewer OK
3. `uv run python scripts/velmo_cli.py` → CLI fonctionne
4. CI verte sur GitHub après push
5. Historique git : commits atomiques (suppressions / archivage / src layout / config / fixes / CI / README)

## 6. Risques et mitigations

| Risque | Mitigation |
|---|---|
| Imports cassés lors du passage à `src/` (~30 fichiers) | migration mécanique + suite de tests complète après chaque étape |
| `sys.path` hacks dans `app_streamlit.py` (lignes 9-10) incompatibles avec le nouveau layout | remplacés par le package installé (`uv sync` installe `velmo` en editable) |
| Makefile/docker-compose avec anciens chemins | passe de vérification dédiée sur tous les fichiers d'infra |
| OneDrive + déplacements de fichiers massifs | opérations via `git mv` (préserve l'historique), vérification `git status` à chaque étape |
