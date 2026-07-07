# Spec — Agent Principal Velmo 2.0 (Chantier 1B)

**Date :** 2026-07-07
**Chantier :** 1B — Orchestration Agent Principal
**Statut :** conception validée, prête pour plan d'implémentation

## Objectif

Construire un agent orchestrateur qui enchaîne memory + guardrails + Kimi LLM pour traiter les messages utilisateur end-to-end. L'agent doit :
1. Accepter un message utilisateur + `user_id`
2. Appliquer garde-fous d'entrée (guardrails input)
3. Enrichir le message avec contexte mémoire (short-term + long-term)
4. Générer une réponse avec Kimi
5. Appliquer garde-fous de sortie (guardrails output)
6. Stocker l'échange en short-term memory
7. Tous les 5 messages : déclencher judge pour extraire faits → long-term memory

Doit fonctionner avec deux interfaces : tests e2e automatisés et CLI interactive.

## Décisions de conception validées

| Sujet | Décision |
|-------|----------|
| Orchestration | Classe `VelmoAgent` unique, responsable de l'ordre des appels |
| Response model | `VelmoResponse` : decision + message + memory context + turn number |
| Guardrails | Appelés via `GuardrailManager.check_input()` et `.check_output()` |
| Memory enrichissement | `MemoryManager.get_context(user_id)` avant Kimi, `.add_exchange()` après |
| Judge trigger | Tous les 5 messages (turns), automatique dans `process_message()` |
| LLM temperature | 0.5 (réalisme > déterminisme) |
| Tests e2e | Rejouent eval/guardrail_cases.jsonl + eval/memory_cases.jsonl |
| CLI interactive | REPL conversationnel, session RAM (pas de persistance) |
| Kimi integration | Appel unique par message, contexte memory concaténé en user prompt |

## Architecture

```
VelmoAgent
├── check_input (guardrails)
│   └─ if blocked → return VelmoResponse(allowed=False, guard_decision)
├── get_context (memory.manager)
├── call Kimi (AzureChatOpenAI + context)
├── check_output (guardrails)
│   └─ if blocked → return VelmoResponse(allowed=False, guard_decision)
├── add_exchange (memory.manager)
└─ every 5 turns → trigger judge (memory.judge.extract_facts)
```

Tests e2e et CLI utilisent `VelmoAgent` via la même interface publique.

## Interface Publique

```python
class VelmoAgent:
    def __init__(self, settings=None, classifier=None, llm=None)
    
    def process_message(self, user_id: str, message: str) -> VelmoResponse
    
class VelmoResponse(BaseModel):
    allowed: bool
    message: str                    # réponse ou safe_message si bloqué
    guard_decision: GuardDecision | None  # si bloqué (input ou output)
    memory_context: dict            # short_term + long_term context utilisé
    turn_number: int                # n-ième message du user
    latency_ms: int                 # temps total processus
```

## Flux de processus

```
user_id, message
   │
   ├─ GuardrailManager.check_input(message)
   │  ├─ if blocked → return REJECT (guard_decision)
   │  └─ if allowed → continue
   │
   ├─ MemoryManager.get_context(user_id)
   │  └─ returns short_term + long_term concatené
   │
   ├─ AzureChatOpenAI.invoke(
   │     system_prompt + memory_context + message
   │  )
   │  └─ response LLM
   │
   ├─ GuardrailManager.check_output(response)
   │  ├─ if blocked → return REJECT (guard_decision)
   │  └─ if allowed → continue
   │
   ├─ MemoryManager.add_exchange(user_id, message, response)
   │  └─ turn_number incremented
   │
   ├─ if turn_number % 5 == 0 → judge.extract_facts(user_id, last_10_messages)
   │  └─ facts → long_term memory (async or sync)
   │
   └─ return VelmoResponse(allowed=True, message=response, ...)
```

## Tests e2e

### Guardrail Cases (eval/guardrail_cases.jsonl)
- 37 cas (24 harmful, 12 legitimate)
- Chaque cas : appelle `process_message()`, valide `response.allowed` vs `expected_action`
- Mesure : block_rate, false_positive_rate

### Memory Cases (eval/memory_cases.jsonl)
- 11 cas conversationnels (recall, persistence, isolation, forget)
- Chaque cas : séquence de `process_message()` appels avec même `user_id`
- Valide que short_term + long_term retiennent les infos attendues
- Mesure : recall_accuracy, isolation_success

### Quality Cases (eval/quality_cases.jsonl)
- 3 cas simples (qualité réponse)
- Valide que réponses contiennent mots-clés attendus

## Interface Interactive (CLI)

**velmo_cli.py** — REPL conversationnel persistant :

```
Welcome to Velmo 2.0 Agent
> user_id: u-test
> msg: Quel est le statut de ma commande 4490 ?

[Input Guard] allowed
[Memory] short_term: 0 turns, long_term: 0 facts
[Kimi] calling...
[Output Guard] allowed
[Turn 1/5 to judge trigger]
Votre commande 4490 est en transit, arrivée prévue demain.

> msg: Quand serai-je livré ?

[Input Guard] allowed
[Memory] short_term: 1 turn, long_term: 0 facts
[Kimi] calling...
[Output Guard] allowed
[Turn 2/5 to judge trigger]
Sous 24 heures ouvrees selon votre commande 4490.
```

Affiche à chaque tour : gardes appliquées, contexte memory, tour_number vs judge trigger.

## Hors périmètre (YAGNI)

- Pas de persistance DB pour la CLI (session RAM)
- Pas de chunking avancé pour memory context
- Pas de queue asynchrone pour judge trigger
- Pas de multi-user concurrence dans la CLI
- Pas de re-ranking semantic pour long-term recall
- Pas de caching des embeddings

## Gestion d'erreurs

| Étape | Erreur | Comportement |
|-------|--------|--------------|
| Input guard | exception | fail-safe : BLOCK |
| Memory get_context | DB down | use empty context, continue |
| Kimi call | timeout/API error | propagate exception, return error response |
| Output guard | exception | fail-safe : BLOCK |
| Memory add_exchange | DB down | log error, don't block response |
| Judge trigger | exception | log error, continue (ne bloque pas next message) |

## Tests

- **Unit** : `VelmoAgent.process_message()` avec mocks (guardrails, memory, Kimi)
- **E2E (guardrails)** : eval/guardrail_cases.jsonl, valide blocking/allowing
- **E2E (memory)** : eval/memory_cases.jsonl, valide recall/persist/isolate
- **Integration** : CLI manuel, teste UX + real memory/Kimi calls
- **Cible** : 100% guardrail cases pass, 90%+ memory cases recall accuracy