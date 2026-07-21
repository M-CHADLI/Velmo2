# Optimisations de latence — Velmo 2.0

> **Document vivant — à conserver et mettre à jour pendant toute la durée du projet.**
> Il justifie chaque choix de performance, trace ce qui est appliqué, et surtout
> ce qui est **volontairement reporté** (avec la raison). Ne pas supprimer.

Dernière révision : 2026-07-09.

---

## 1. Contexte — profil de latence mesuré

Chemin critique d'un message (`VelmoAgent.process_message`). Latences **mesurées**
depuis la base (`guardrail_log`, `extraction_metadata`) ou **estimées** quand
l'étape n'est pas instrumentée.

| Étape | Backend | Latence | Source |
|-------|---------|--------:|--------|
| Règles regex (input) | CPU | < 1 ms | estimé |
| **Classifier input** (garde-fou LLM) | model-router | **4 505 ms** (p95 6 253) | mesuré (n=19) |
| `get_context` (short-term RAM + pgvector long-terme) | RAM + Postgres | ~330 ms | estimé |
| **Génération réponse** | model-router | **~4 000 ms** | estimé |
| Output guard (regex PII) | CPU | **0 ms** | mesuré (n=16) |
| `write_log` guardrail ×2 | Postgres | ~10 ms | estimé |
| **Juge — `extract_facts`** (1 tour/5) | model-router | **5 610 ms** | mesuré (n=2 ⚠️) |
| **Persist facts** (embed + HNSW, 1 tour/5) | Postgres | **6 353 ms** | mesuré (n=2 ⚠️) |

**Tour typique ≈ 8,9 s** · **Tour avec juge ≈ 20,8 s**.

Constat clé : **deux appels LLM séquentiels** (classifier puis réponse) sur le
même `model-router` représentent ~8,5 s des ~8,9 s. Le short-term est en RAM
(`memory/short_term.py`), donc négligeable. L'output guard (regex) est déjà optimal.

---

## 2. Décisions appliquées ✅

### D1 — Plafonner `max_tokens` du classifier (+ déploiement dédiable)
**Fichiers :** `memory/config.py`, `guardrails/classifier.py`, `.env.example`

Le classifier ne renvoie qu'**un mot** de catégorie, mais sans borne le modèle
peut générer une explication et la latence d'un LLM est dominée par le nombre de
tokens produits. On plafonne à `CLASSIFIER_MAX_TOKENS=10`.

En complément, `CLASSIFIER_DEPLOYMENT_NAME` permet de pointer le classifier vers
un **modèle plus léger/rapide** (ex. `gpt-4o-mini`, `haiku`) sans toucher au
modèle de réponse. Par défaut = déploiement principal (aucune régression).

- **Pourquoi** : poste de latence n°1, sur *chaque* message, bloquant avant la réponse.
- **Gain MESURÉ** : `model-router` **4 505 ms** → `gpt-5.4-mini` **~1 500 ms** (≈ 3× plus rapide).
- **Config retenue** : `CLASSIFIER_DEPLOYMENT_NAME=gpt-5.4-mini`, `CLASSIFIER_MAX_TOKENS=16`.
- **Notes déploiement Azure** :
  - Seuls les modèles réellement **déployés dans la ressource pointée par
    `AZURE_OPENAI_ENDPOINT`** sont appelables ; le catalogue `/models` liste bien
    plus que ce qui est déployé (vérifier par un appel réel, pas par le catalogue).
  - `gpt-5.4-mini` (famille GPT-5) exige `max_completion_tokens` (≥ 16) et refuse
    `temperature` custom. **`langchain-openai` ≥ 1.3.3 gère ces contraintes
    automatiquement** — aucun code spécifique requis.
  - Minimum 16 tokens imposé par ces modèles → défaut `CLASSIFIER_MAX_TOKENS` relevé
    de 10 à 16. Si une catégorie ressort vide/`out_of_scope` par défaut, monter ce cap.

### D2 — Plafonner `max_tokens` de la réponse
**Fichiers :** `memory/config.py`, `agent/agent.py`, `.env.example`

`RESPONSE_MAX_TOKENS=512` borne la latence pire-cas de la génération. Les réponses
du support sont courtes.

- **Pourquoi** : 2ᵉ poste de latence (~4 s).
- **Gain attendu** : borne le pire cas ; le vrai gain de latence *perçue* viendra
  du streaming (voir D5, reporté).
- **Risque** : réponses tronquées si 512 tokens sont insuffisants → ajustable par env.

---

## 3. Décisions reportées ⏳ (et pourquoi)

> **Blocant transverse : la connexion PostgreSQL est un singleton unique partagé**
> (`memory/database.py::get_db`) en `autocommit=False`. Une connexion psycopg
> **n'est pas thread-safe**. Toute parallélisation qui fait de la DB sur un thread
> pendant qu'un autre thread écrit sur la même connexion corrompt l'état.
> **Ce point doit être résolu (pool de connexions ou connexion dédiée par thread)
> avant D3 et D4.**

### D3 — Rendre le juge asynchrone (retirer ~12 s du 5ᵉ tour) — **BLOQUÉ**
Le juge (5,6 s) + la persistance (6,3 s) tournent en **synchrone** dans le Stage 6
de `agent.py` et ajoutent ~12 s au tour utilisateur. Les passer en tâche de fond
retirerait ce pic. **Bloqué** car le thread de fond écrirait les facts via la
connexion partagée pendant que le tour suivant l'utilise → race condition.
**Prérequis** : donner au juge sa propre connexion (`Database(connection_url)` dédiée)
ou un pool.

### D4 — Paralléliser `get_context` et le classifier — **BLOQUÉ**
Les deux sont indépendants (~330 ms récupérables) mais `get_context` (lecture DB)
et `write_log` du classifier (écriture DB) partagent la connexion unique.
**Prérequis** : idem D3 (pool / connexion par tâche).

### D5 — Streamer la réponse vers l'UI Streamlit — **à faire**
Réduit la latence *perçue* de ~4 s au premier token. Nécessite `llm.stream()` +
`st.write_stream()` dans `streamlit/` et une adaptation de `ChatHandler`.
Non bloqué techniquement, mais refactor plus large → planifié séparément.

### D6 — Corriger la persistance à 6,3 s — **à investiguer**
`db_latency_ms = 6 353 ms` est anormal (n=2 seulement). Voir §4.

---

## 4. Lacune d'instrumentation ⚠️

`extraction_metadata.embedding_latency_ms` est enregistré à **0** : l'embedding
des facts (appel réseau Azure `text-embedding-3-small`) n'est pas mesuré. Cela
masque probablement une partie du coût attribué à `db_latency_ms` (6,3 s).

**Action requise avant D6** : mesurer réellement la latence d'embedding dans
`memory/long_term.py::_get_embedding`, puis décider (batching d'embeddings,
index HNSW différé, etc.).

Depuis le Chantier 3, **LangSmith** capture désormais en continu
`response_latency_ms`, `judge_latency_ms`, `judge_confidence` et `blocked` —
ce qui remplacera à terme les estimations de ce document par des mesures.

---

## 5. Tableau de suivi

| ID | Optimisation | Portée | Statut | Gain visé |
|----|--------------|--------|--------|-----------|
| D1 | Classifier : gpt-5.4-mini + max_tokens=16 | chaque message | ✅ appliqué | **4,5 s → ~1,5 s (mesuré)** |
| D2 | Réponse : max_tokens | chaque message | ✅ appliqué | borne le pire cas |
| D3 | Juge asynchrone | 1 tour/5 | ⏳ bloqué (connexion) | −12 s sur le 5ᵉ tour |
| D4 | Paralléliser contexte + classifier | chaque message | ⏳ bloqué (connexion) | −330 ms |
| D5 | Streaming de la réponse | chaque message | ⏳ à faire | latence perçue |
| D6 | Persistance 6,3 s + embedding | 1 tour/5 | ⏳ à investiguer | ~6 s → ~1 s |
| — | Pool / connexion DB dédiée par thread | infra | ⏳ prérequis D3/D4 | débloque D3, D4 |

---

## 6. Comment ajuster (opérateur)

Variables d'environnement (voir `.env.example`) :

```bash
CLASSIFIER_DEPLOYMENT_NAME=   # vide = même modèle que la réponse
CLASSIFIER_MAX_TOKENS=10      # augmenter si une catégorie est tronquée
RESPONSE_MAX_TOKENS=512       # augmenter si les réponses sont coupées
```
