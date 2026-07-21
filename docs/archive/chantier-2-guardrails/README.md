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

## Fichiers de Documentation

| Fichier | Contenu | Audience |
|---------|---------|----------|
| **[01_DESIGN.md](./01_DESIGN.md)** | Architecture complète (guards, flux, configuration YAML) | Architects |
| **[02_SCHEMAS.md](./02_SCHEMAS.md)** | Pydantic models pour tous les schemas + exemples | Developers |
| **[03_FLOWCHARTS.md](./03_FLOWCHARTS.md)** | 11 diagrammes Mermaid (pipelines, COT, PII, etc.) | Visual learners |
| **[04_OPTIMIZATIONS.md](./04_OPTIMIZATIONS.md)** | Parallélisation + gains latence (540ms → 260ms) | Developers |
| **[05_TABLEAU_GARDEFOUS.md](./05_TABLEAU_GARDEFOUS.md)** | Tableau catégorie × emplacement × méthode × action (livrable brief) | Formateur / Architects |

---

## Décisions Validées (2026-07-02)

| Aspect | Décision | Détails |
|--------|----------|---------|
| **PII Strategy** | Redacter (complet) | Input + Output + Storage |
| **Safety Errors** | Chain-of-Thought | Double vérification si confiance < 0.75 |
| **Rate Limiting** | Sliding window 2-tier | 2 req/sec (soft) + 100 req/h (hard) |
| **Compliance** | MVP simple | Full legal review des logs ultérieurement |
| **Integration C1** | Redacted facts only | Judge/LLM jamais PII brutes |
| **Error Handling** | Fail open | Rejeter si guard échoue (sécurité) |
| **Latency Budget** | < 500ms acceptable | Optimisé: ~260ms avec parallélisation |
| **Monitoring** | 4 KPIs | Rejection rates, latency p95, PII accuracy, uptime |

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
