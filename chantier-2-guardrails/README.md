# Chantier 2: Guardrails (Protection Input/Output)

## Objectif

Assurer que **tous les messages (input et output) respectent les règles de sécurité et conformité** avant d'être traités par la mémoire ou envoyés à l'utilisateur.

---

## Composants Principaux

### Input Guardrails

1. **Validation de schéma** (Pydantic)
   - Format du message valide
   - Longueur + caractères autorisés
   - Métadonnées complètes

2. **Classification de sécurité** (Kimi 2.6)
   - Spam, hate speech, violence
   - Phishing, malware mentions
   - Adult/NSFW content

3. **Détection PII** (Presidio)
   - Identifiants sensibles
   - Numéros de carte
   - Emails, téléphones (contextuel)

4. **Limitation de débit** (Redis)
   - Max 100 req/hour par user
   - Throttle aggressif pour patterns suspects

### Output Guardrails

1. **Redaction PII** (Custom)
   - Masquer secrets présents dans réponse
   - Redact tokens, API keys, etc.

2. **Conformité GDPR/CNIL** (Custom rules)
   - Vérifier aucune donnée perso exposée
   - Respecter preferences utilisateur

3. **Audit logging** (PostgreSQL)
   - Chaque décision tracée
   - Raison du rejet (si applicable)

---

## Fichiers de Conception

- **01_DESIGN.md** — Architecture détaillée, flux décision, règles
- **02_SCHEMAS.md** — JSON schemas, validation rules
- **03_DIAGRAMMES.md** — Diagrams (Mermaid)
- **04_DECISIONS.md** — Decision matrix (outils, tradeoffs)

---

## Fichiers Schemas

```
schemas/
├── user_message.schema.json      — Message input validation
├── guardrail_decision.schema.json — Decision output
└── audit_event.schema.json       — Audit log entry
```

---

## Intégration avec Chantier 1 & 3

- **← Chantier 1**: Reçoit messages validés seulement
- **→ Chantier 1**: Filtre output avant user
- **→ Chantier 3**: Log chaque décision pour monitoring

---

## Quick Start

```python
from chantier_2_guardrails import GuardrailsPipeline

pipeline = GuardrailsPipeline(user_id="karim-123")

# Input
if pipeline.validate_input(message):
    # Safe to process
    pass

# Output
safe_response = pipeline.filter_output(response)
```

---

## Next: Read [01_DESIGN.md](./01_DESIGN.md)
