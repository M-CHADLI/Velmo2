[📖 Documentation](../../README.md) › [Chantiers](../../README.md) › Chantier 1 — Mémoire

# 🧠 Chantier 1 — Mémoire

**Objectif :** l'agent doit être remarquablement bon pour se souvenir — sur une
même conversation (fil long) comme d'une session à l'autre (jours plus tard).

Code : [`src/velmo/memory/`](../../../src/velmo/memory/)

## Les 3 couches de mémoire

```mermaid
flowchart TB
    subgraph Manager["VelmoMemoryManager (chef d'orchestre)"]
        ST["🩳 Court terme<br/>SlidingWindowMemory<br/>30 derniers messages<br/>(par utilisateur, en RAM)"]
        JUDGE["⚖️ Judge<br/>JudgeAgent<br/>extrait les faits durables<br/>(toutes les 5 tours)"]
        LT["🗄️ Long terme<br/>LongTermMemory<br/>PostgreSQL + pgvector<br/>(faits + embeddings)"]
    end
    ST -->|toutes les 5 tours| JUDGE
    JUDGE -->|faits confiance ≥ 0.8| LT
    LT -->|recherche sémantique| CTX["Contexte injecté dans le prompt"]
    ST --> CTX
```

| Couche | Fichier | Rôle | Où c'est stocké |
|--------|---------|------|-----------------|
| **Court terme** | `short_term.py` | Les 30 derniers messages de la conversation en cours | En mémoire vive (par `user_id`) |
| **Judge** | `judge.py` | Lit les 10 derniers messages et en extrait des **faits durables** (JSON structuré) | — (c'est un appel LLM) |
| **Long terme** | `long_term.py` | Faits + préférences + identifiants, cherchables sémantiquement | PostgreSQL (table `facts` + `pgvector`) |

Le tout est coordonné par `VelmoMemoryManager` ([`manager.py`](../../../src/velmo/memory/manager.py)).

## Comment un fait est mémorisé, puis retrouvé

```mermaid
sequenceDiagram
    participant U as 👤 Client
    participant M as VelmoMemoryManager
    participant ST as Court terme
    participant J as Judge (LLM)
    participant LT as Long terme (pgvector)

    U->>M: "Mon numéro de contrat est CT-7788"
    M->>ST: record_user_message()
    Note over M: Toutes les 5 tours, l'agent<br/>déclenche l'extraction
    M->>J: extract_facts(10 derniers messages)
    J-->>M: {key: contract_id, value: CT-7788, confidence: 0.95}
    M->>LT: store_fact() (si confiance ≥ 0.8)<br/>+ embedding du fait

    Note over U,LT: ... plus tard, même ou nouvelle session ...
    U->>M: "C'est quoi mon numéro de contrat ?"
    M->>LT: get_conversation_context(question)
    LT-->>M: recherche sémantique → "contract_id: CT-7788"
    M-->>U: le contexte est injecté → l'agent répond "CT-7788"
```

**Points clés du code :**
- Le Judge n'extrait que les faits **explicites et durables** (identifiants, préférences, infos stables), jamais les détails jetables.
- Seuls les faits de **confiance ≥ 0,8** (`confidence_threshold`) sont stockés.
- La recherche long terme est **sémantique** : `retrieve_context()` compare l'embedding de la question aux embeddings des faits (opérateur `<=>` de pgvector).

## Réponse aux 6 exigences du brief (R1–R6)

| # | Exigence | Comment c'est réalisé |
|---|----------|-----------------------|
| **R1** | Tenir 30+ tours sans perdre une info du début | L'info donnée tôt est extraite en **long terme** par le Judge → elle survit même quand elle sort de la fenêtre court terme |
| **R2** | Se souvenir d'une session à l'autre | La mémoire longue est **persistée en base** (indépendante de la session) |
| **R3** | Isolation stricte entre utilisateurs | Tout est stocké et recherché **par `user_id`** (jamais de fuite d'un client à l'autre) |
| **R4** | Tenir la fenêtre de contexte | **Fenêtre glissante 30 messages** + récupération **sélective** des k faits pertinents (pas tout le passé) |
| **R5** | Droit à l'oubli (RGPD) | `check_and_handle_forget_request()` détecte « oublie/supprime/efface… » → **soft delete** vérifiable (`delete_fact_gdpr`) |
| **R6** | Traçabilité | `inspect_memory(user_id)` liste ce qui est retenu + `get_audit_trail(user_id)` trace les opérations |

## Réglages (dans `config.py`)

| Paramètre | Valeur par défaut | Effet |
|-----------|-------------------|-------|
| `short_term_max_messages` | 30 | Taille de la fenêtre court terme |
| `extraction_trigger_frequency` | 5 | Le Judge tourne toutes les 5 tours |
| `confidence_threshold` | 0.8 | Confiance minimale pour stocker un fait |
| `embedding_model` | text-embedding-3-small | Modèle d'embedding (384 dimensions) |

> ⚠️ La mémoire longue dépend d'un **modèle d'embedding déployé** sur Azure. Sans lui,
> la recherche sémantique retombe sur des vecteurs « mock » et ne retrouve plus rien —
> voir la démonstration dans le [Chantier 3 (notation)](../3-qualite/notation.md).

---

**Voir aussi :** [Architecture globale](../../architecture.md) ·
[Chantier 2 — Garde-fous](../2-guardrails/README.md) ·
[Chantier 3 — Qualité (comment on teste la mémoire)](../3-qualite/README.md)

⬆ [Retour à l'index](../../README.md)
