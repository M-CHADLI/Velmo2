# Spec — Module `guardrails/` (Velmo 2.0)

**Date :** 2026-07-07
**Chantier :** 2 — Garde-fous
**Statut :** conception validée, prête pour plan d'implémentation

## Objectif

Empêcher Velmo 2.0 de traiter (entrée) ou produire (sortie) des contenus interdits. Chaque blocage renvoie un refus poli et est journalisé. Le module doit faire passer les tests d'acceptance de `eval/guardrail_cases.jsonl`.

**Catégories couvertes** (d'après le brief et les cas de test) :
- **Entrée à bloquer** : `hate`, `violence`, `sexual`, `prompt_injection`, `secret_leak`, `out_of_scope`
- **Sortie à bloquer** : `pii` (carte bancaire, mot de passe, IBAN)
- **Légitimes à laisser passer** : messages de support e-commerce

## Décisions de conception validées

| Sujet | Décision |
|-------|----------|
| Architecture | Pipeline de checks modulaires (un composant = une responsabilité) |
| Détection entrée | Hybride : règles regex + classifieur LLM Kimi |
| Détection sortie | Regex uniquement (PII = formats déterministes) |
| Décision sortie PII | Bloquer la réponse entière (conforme `expected_action="block"`) |
| Message de refus | Générique unique : « Je ne peux pas traiter cette demande. Je suis l'assistant du support Velmo — reformulez et je vous aide avec plaisir. » |
| Journalisation | Table `guardrail_log` en PostgreSQL |
| Fallback classifieur | Retry (2 tentatives, court délai) puis **fail-safe** (bloquer si Kimi reste KO) |
| LangFuse | Découplé : branché via CallbackHandler au niveau du classifieur, `guardrails/` n'en dépend pas |

## Architecture

```
guardrails/
├── manager.py       # GuardrailManager : orchestre check_input / check_output
├── input_guard.py   # logique hybride règles → Kimi
├── output_guard.py  # scan regex PII sur la réponse
├── rules.py         # motifs regex + listes (injection, secrets, PII)
├── classifier.py    # appel Kimi (pattern miroir de memory/judge.py)
├── schema.py        # GuardDecision (Pydantic)
└── audit.py         # écriture PostgreSQL guardrail_log
```

Chaque unité a une responsabilité unique, une interface claire, et est testable isolément.

## Interface publique

```python
class GuardrailManager:
    def check_input(self, message: str, user_id: str) -> GuardDecision
    def check_output(self, response: str, user_id: str) -> GuardDecision
```

```python
class GuardDecision(BaseModel):
    allowed: bool                 # True = laisser passer
    category: str                 # "legitimate", "hate", "pii", ...
    where: str                    # "input" | "output"
    safe_message: str | None      # message de refus générique si bloqué
    reason: str                   # détail interne (pour le log)
    latency_ms: int
```

`GuardDecision` est la sortie unique des deux méthodes (entrée et sortie).

## Flux dans l'agent

```
message user
   ├─ check_input() ── bloqué ? ▶ safe_message + log, STOP (LLM jamais appelé)
   │        │ allowed
   │        ▼  mémoire + LLM → response
   └─ check_output() ── bloqué ? ▶ safe_message + log, STOP
            │ allowed
            ▼  response envoyée à l'utilisateur
```

Dès qu'un garde bloque : retour du `safe_message`, journalisation, court-circuit.

## Garde-fou d'entrée (`input_guard.py`)

Deux étages, du moins cher au plus cher, arrêt dès blocage :

**Étage 1 — Règles (`rules.py`), instantané et déterministe :**
- `prompt_injection` : motifs « ignore tes instructions », « oublie tes consignes », « developer mode », « révèle/affiche ton prompt système »
- `secret_leak` : « clé api », « mot de passe de la base », « variables d'environnement », « tokens internes », « secret de configuration »
- match ▶ BLOCK, on s'arrête.

**Étage 2 — Classifieur Kimi (`classifier.py`), pour le nuancé :**
- 1 appel LLM, `temperature=0`, retourne UNE catégorie : `hate | violence | sexual | out_of_scope | legitimate`
- catégorie interdite ▶ BLOCK ; `legitimate` ▶ ALLOW.

**Ordre justifié :** injection et secrets ont des formulations typées → regex fiable et gratuit. Hate/violence/scope sont nuancés → le LLM comprend le contexte.

**Anti-faux-positifs :** les regex ne matchent que des motifs très spécifiques, jamais des chiffres seuls. « Statut de ma commande 4490 » ne déclenche aucune règle → LLM → `legitimate`.

**Fallback :** si l'appel Kimi échoue, retry (2 tentatives, court délai) ; si toujours KO ▶ fail-safe = BLOCK (catégorie `classifier_error`). Sécurité avant utilité. La journalisation permet de mesurer ces cas.

## Garde-fou de sortie (`output_guard.py`)

Scan **regex uniquement** de la réponse LLM :
- carte bancaire : `\b(?:\d[ -]?){13,16}\b`
- IBAN : `\b[A-Z]{2}\d{2}[ ]?(?:[A-Z0-9]{4}[ ]?){2,}`
- mot de passe : `mot de passe ... : <valeur>`, `password: ...`
- match ▶ BLOCK (`category="pii"`, réponse entière remplacée par le `safe_message`) ; rien ▶ ALLOW.

Pas de LLM : une carte ou un IBAN est un motif, pas une nuance de sens. Regex = instantané, gratuit, déterministe. C'est la 2ᵉ barrière (défense en profondeur).

## Audit (`audit.py`)

```sql
CREATE TABLE guardrail_log (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    where_      TEXT NOT NULL,        -- 'input' | 'output'
    category    TEXT NOT NULL,        -- 'hate', 'pii', 'legitimate', ...
    allowed     BOOLEAN NOT NULL,
    reason      TEXT,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

Toute décision (bloquée ou non) est journalisée. Rend requêtables le taux de blocage et le taux de faux positifs (signaux du chantier 3), et satisfait l'exigence « journalise l'événement » + traçabilité RGPD.

## Articulation avec LangFuse

Rôles complémentaires, sans doublon :
- **PostgreSQL `guardrail_log`** = source de vérité audit/compliance (le *quoi* : quelle décision, pour qui). Persistant, testable hors-ligne, exigé par le brief.
- **LangFuse** = observabilité (le *comment ça tourne* : latence, tokens, coût de l'appel Kimi).

Couplage **découplé** : `guardrails/` écrit uniquement son audit PostgreSQL. LangFuse est branché au niveau du classifieur Kimi via le `CallbackHandler` LangChain — il capture automatiquement les traces LLM sans que `guardrails/` dépende de LangFuse. Le module reste autosuffisant et testable sans service externe.

## Gestion d'erreurs

| Étage | Erreur | Comportement |
|-------|--------|--------------|
| Règles regex | aucune (pur local) | — |
| Classifieur Kimi | timeout / API | retry 1-2× → sinon fail-safe (BLOCK) |
| Audit PostgreSQL | DB down | log l'erreur, ne bloque pas la décision déjà prise |

## Tests

- **Unitaires** : `rules.py` (chaque regex), `output_guard` (carte/IBAN/password), `input_guard` avec Kimi **mocké** (aucun appel réseau en test).
- **Acceptance** : script rejouant `eval/guardrail_cases.jsonl` — pour chaque cas, appelle `check_input`/`check_output` selon `where`, compare `allowed` à `expected_action`. Mesure taux de blocage et taux de faux positifs.
- **Cible** : 100 % des toxiques bloqués, 0 faux positif sur les 12 légitimes.

## Hors périmètre (YAGNI)

- Pas de rate limiting (absent des cas de test et des catégories du brief).
- Pas de Redis, Presidio, ni chain-of-thought multi-passes (sur-dimensionnés pour l'exercice ; la doc `chantier-2-guardrails/` reste une réf conceptuelle, pas la cible de code).
- Pas de redaction partielle en sortie (les tests exigent le blocage).
