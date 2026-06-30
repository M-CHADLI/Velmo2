# Cas d'usage — Chantier 1 : Mémoire

**Scénarios concrets** pour valider le design et guider l'implémentation.

---

## Cas 1 — R1 : Tenir 30+ tours

### Scenario

L'utilisateur Karim a une conversation de 35 tours :
- **Tour 1** : "Bonjour, je suis Karim. Mon numéro de contrat est KX-4471."
- **Tours 2–30** : Conversation diverse sur d'autres sujets
- **Tour 31** : Karim demande "Rappelle-moi mon numéro de contrat"

### Expected behavior

Agent doit répondre **correctement** : "Votre numéro de contrat est KX-4471."

### How memory handles it

```
Tour 1: Message arrive
  → Fenêtre glissante (court terme): +1 message
  → (< 10 messages, pas de judge)

Tours 2–10: Messages normaux
  → Fenêtre glissante: +9 messages (total 10)

Tour 10: Judge exécute
  → Lit 10 messages bruts (including tour 1)
  → Extrait: fact_id="f1", key="contract_number", value="KX-4471"
  → Persiste avec confidence=0.99, source="user_statement"
  → Embedding créé
  → Stocké en base long terme

Tours 11–30: Messages normaux
  → Fenêtre glissante continue
  → Tour 1 peut avoir quitté la fenêtre (FIFO)

Tour 31: Karim demande "Rappelle-moi..."
  → Fenêtre glissante: message 31 ajouté
  → (pas 10 nouveaux messages depuis tour 10, pas de judge)
  → AVANT appel LLM:
     → Recherche vectorielle: "contrat numéro" → retrouve fact_id="f1"
     → Score de pertinence: HIGH
     → Injection: "Faits retenus: Contrat=KX-4471"
  → LLM reçoit: contexte (faits injectés) + fenêtre (tours récents)
  → LLM génère: "Votre contrat est KX-4471"
  → Réponse correcte ✅

Test assertion: Agent récite correctement la valeur du tour 1
```

### Test d'acceptance (BDD)

```gherkin
Scenario: Remembering info from tour 1 in tour 30+
  Given a conversation of 35 turns
  And tour 1 contains "contract_number = KX-4471"
  And tours 2-30 contain diverse topics (no mention of contract)
  When user asks at tour 31 "remind me my contract"
  Then agent responds with "KX-4471"
  And memory log shows fact was retrieved from persistent memory
```

---

## Cas 2 — R2 : Mémoire multi-session

### Scenario

**Session 1** (30 juin 10:00) :
- Karim parle à l'agent
- Mentionne : nom, contrat, type compte (pro)
- Conversation longue, puis ferme navigateur

**Session 2** (1 juillet 09:00 — 23 heures plus tard) :
- Karim ouvre une nouvelle conversation
- Demande : "Bonjour, rappelle-moi ce que tu sais de moi"

### Expected behavior

Agent doit se souvenir **des facts durables** d'une session à l'autre :
- Nom : Karim ✓
- Contrat : KX-4471 ✓
- Type : Pro ✓

### How memory handles it

```
SESSION 1 (30 juin)
  Tour 1–10: Judge extrait 3 facts
    → f1: key="name", value="Karim", type="identifier", conversation_id="conv_20260630_001"
    → f2: key="contract_number", value="KX-4471"
    → f3: key="account_type", value="pro", type="status"
  → Persiste en: users_karim_123_facts (relational DB)
  → Embedding stocké en vectorDB namespace karim_123
  → Session 1 termine

SESSION 2 (1 juillet, +23h)
  Tour 1: Karim dit bonjour
    → Fenêtre glissante: vide (nouvelle session)
    → AVANT appel LLM:
       → Recherche vectorielle: "ce que tu sais de moi"
       → Retrouve 3 facts: name, contract, account_type
       → Score: HIGH pour tous
       → Injection: "Faits retenus: Karim, Pro, Contrat KX-4471"
  → LLM reçoit contexte
  → LLM génère: "Bonjour Karim! Je me souviens: vous êtes Pro avec contrat KX-4471"
  → Réponse correcte ✅

Test assertion: Facts survivent à la fin de session ET réapparaissent session suivante
```

### Test d'acceptance (BDD)

```gherkin
Scenario: Remembering facts across sessions
  Given session 1 stores facts: name=Karim, contract=KX-4471, type=Pro
  When session 1 ends
  And session 2 starts (23 hours later, same user)
  And user asks "remind me what you know about me"
  Then agent mentions name, contract, type
  And facts come from persistent memory (not current session)
```

---

## Cas 3 — R3 : Isolation stricte

### Scenario

**User A** (Karim) : contrat KX-4471
**User B** (Alice) : contrat KX-9999

Deux sessions parallèles ou en série, on doit s'assurer aucun croisement.

### Expected behavior

- Karim demande son contrat → obtient KX-4471 ✓
- Alice demande son contrat → obtient KX-9999 ✓
- Jamais de confusion

### How memory handles it

```
CREATE TABLE users_karim_123_facts (...)
  ├─ fact_id="f_k1", key="contract", value="KX-4471"
  └─ ...

CREATE TABLE users_alice_456_facts (...)
  ├─ fact_id="f_a1", key="contract", value="KX-9999"
  └─ ...

VectorDB Namespace: karim_123
  └─ Contient UNIQUEMENT embeddings de karim

VectorDB Namespace: alice_456
  └─ Contient UNIQUEMENT embeddings d'alice

Request: Karim demande son contrat
  → user_id = "karim_123" (from JWT)
  → Query: SELECT * FROM users_karim_123_facts WHERE ...
  → Résultat: KX-4471 ✅

Request: Alice demande son contrat
  → user_id = "alice_456"
  → Query: SELECT * FROM users_alice_456_facts WHERE ...
  → Résultat: KX-9999 ✅

Injection prompt (Karim):
  "Contexte: Contrat=KX-4471"

Injection prompt (Alice):
  "Contexte: Contrat=KX-9999"

Jamais de cross-contamination ✓
```

### Test d'acceptance (BDD)

```gherkin
Scenario: Strict user isolation
  Given user A (karim) has contract KX-4471
  And user B (alice) has contract KX-9999
  When user A queries "my contract"
  Then user A gets "KX-4471"
  And user B's data is NOT accessible
  
  When user B queries "my contract"
  Then user B gets "KX-9999"
  And user A's data is NOT accessible
```

---

## Cas 4 — R5 : Droit à l'oubli

### Scenario

**Session** :
- Tour 1 : "Mon numéro de carte est 1234-5678-9012-3456" (extracted as fact)
- Tours 2–15 : Conversation normale
- Tour 16 : "Oublie mon numéro de carte"

### Expected behavior

- Fact doit être effectivement supprimé
- Vérification : requête suivante ne retrouve pas le fact
- Historique conservé (audit)

### How memory handles it

```
Tour 1: Message arrive
  → Fenêtre glissante: +1 msg
  → Judge (après 10 msgs) extrait:
    fact_id="f_card", key="card_number", value="1234-...", 
    sensitivity="high", pii_category="payment_card"
  → Persisté + embedding

Tours 2–15: Normal

Tour 16: "Oublie mon numéro de carte"
  → Agent détecte: deletion_request
  → Extracte: pii_category="payment_card" OR key="card_number"
  → Requête: SELECT fact_id FROM users_karim_123_facts 
            WHERE pii_category="payment_card"
  → Trouve: f_card
  → UPDATE users_karim_123_facts 
    SET status="soft_deleted", 
        deletion_reason="user_requested_on_2026-06-30T12:30:00Z"
    WHERE fact_id="f_card"
  → VectorDB: Marquer fact comme supprimé (metadata update)
  
Tour 17: LLM appelle recherche vectorielle
  → Recherche: "carte" ou "payment"
  → VectorDB filtre: WHERE status != "soft_deleted"
  → Fact f_card n'apparaît PAS ✓
  → Injection prompt: pas de mention du numéro
  → LLM: "Vos données de paiement ont été oubliées"

Vérification (Chantier 3):
  → Query: SELECT * FROM users_karim_123_facts WHERE status="active"
  → f_card n'apparaît pas ✓
  → Query: SELECT * FROM users_karim_123_facts (tous)
  → f_card apparaît avec status="soft_deleted" (audit trail) ✓
```

### Test d'acceptance (BDD)

```gherkin
Scenario: Right to be forgotten (GDPR)
  Given fact: card_number="1234-5678-9012-3456", status=active
  When user requests "forget my card number"
  Then fact status = "soft_deleted"
  And fact is NOT returned by search queries
  And fact still exists in DB (audit trail preserved)
  
  When next agent query searches memory
  Then card number does NOT appear
  And agent does NOT mention card details
```

---

## Cas 5 — R4 : Budget tokens (fenêtre glissante)

### Scenario

Budget: 100k tokens
Average message: ~150 tokens each

A très long conversation (100+ tours) → fenêtre approche du limite

### Expected behavior

- Tours anciens quittent la fenêtre (FIFO)
- Judge capture les infos critiques avant qu'elles sortent
- Fenêtre reste < 80% du budget

### How memory handles it

```
Token budget: 100k

Tours 1–40 (normal state)
  Fenêtre = 40 * 150 * 2 = 12,000 tokens (12%)
  Available space: 88,000 tokens

Tour 41–200 (conversation gets very long)
  Fenêtre grow towards 80k tokens
  Judge exécute tous les 10 messages
  → Extraction des infos critiques AVANT elles sortent
  
Tour 201 (fenêtre at 85k tokens = 85% limit)
  → Alert: fenêtre > 80% du budget
  → Action: Tours 1–5 (oldest) sont DROPPED from window
  → Freed: ~1,500 tokens
  → Fenêtre: 83,500 tokens (83%)
  
Tour 202–210 (continue)
  → Judge exécute
  → Infos de tours 201–210 extraites
  → Persistées

Invariant: Fenêtre n'excède JAMAIS 100k tokens
Effect: Aucune info critique perdue (car judge a extrait)
```

### Test d'acceptance (BDD)

```gherkin
Scenario: Context window management
  Given budget = 100k tokens, current window = 80k tokens
  When new message arrives (500 tokens)
  And window would exceed 100k
  Then oldest messages are dropped (FIFO)
  And window stays within budget
  
  Given judge runs before window drops critical message
  Then critical info is extracted and persisted
  And window can safely drop raw message
```

---

## Cas 6 — Judge quality monitoring (pour Chantier 3)

### Scenario

Test qu'on peut détecter si le judge fonctionne mal.

**Scenario A** : Judge hallucine (extrait faux)
```
Tour 1: "Mon nom est Karim"
Judge: fact extracted: key="name", value="Karim", confidence=0.99 ✓

Tour 2: "Je suis venu pour un problème de facturation"
Judge: fact extracted: key="problem_type", value="BILLING", confidence=0.85
       MAIS AUSSI: key="account_balance", value="€500", confidence=0.1
       (hallucination — jamais dit)

Chantier 3: 
  → Detect low confidence (0.1) on "account_balance"
  → Alert: judge unsure
  → In evaluation: fact not in ground truth → FLAG
  → Monitoring: confidence scores histogram
```

**Scenario B** : Judge misses info (recall failure)
```
Tour 1: "Mon nom est Karim, mon email est karim@example.com"
Judge: Extrait JUSTE "name", manque "email"

Chantier 3:
  → Ground truth says: 2 facts expected (name + email)
  → Judge found: 1 fact
  → Recall = 1/2 = 50% ❌
  → Alert: judge missing info
```

### Test d'acceptance (BDD)

```gherkin
Scenario: Judge quality is measurable
  Given judge extracts facts from conversation
  When evaluation suite runs (Chantier 3)
  Then confidence scores are logged
  And recall/precision metrics are computed
  And low confidence facts are flagged
  And missing facts (vs ground truth) are detected
```

---

## Cas 7 — Version history (tracing updates)

### Scenario

Karim changes his contract number over time.

```
Tour 1: "Mon contrat: KX-4471"
  → Judge (after 10 msgs): creates f1, version=1, value="KX-4471"

Tours 2–25: Normal

Tour 26: "J'ai changé, nouveau contrat: KX-9999"
  → Judge (after 10 msgs): updates f1
    version_history:
      [
        {version: 2, value: "KX-9999", message: 26, timestamp: "...", reason: "user_update"},
        {version: 1, value: "KX-4471", message: 1, timestamp: "..."}
      ]

Tours 27–50: Normal

Tour 51: "Non attends, le vrai numéro c'est KX-8888"
  → Judge: updates f1 again
    version_history:
      [
        {version: 3, value: "KX-8888", message: 51, reason: "correction"},
        {version: 2, value: "KX-9999", message: 26},
        {version: 1, value: "KX-4471", message: 1}
      ]
    (Note: keeps max 3, oldest v1 eventually trimmed)
```

### Inspection query (R6)

```
GET /memory/karim_123/facts/f1
→
{
  "fact_id": "f1",
  "key": "contract_number",
  "value": "KX-8888",
  "version_history": [
    {version: 3, value: "KX-8888", message: 51},
    {version: 2, value: "KX-9999", message: 26},
    {version: 1, value: "KX-4471", message: 1}
  ]
}

Audit insight: Can trace how value evolved, confidence changes
```

---

## Summary — Test acceptance checklist

- [ ] **R1** : 30+ tour test passes (info from turn 1 retrieved in turn 31)
- [ ] **R2** : Multi-session test passes (facts persist across sessions)
- [ ] **R3** : Isolation test passes (no cross-user contamination)
- [ ] **R4** : Window management test passes (budget respected, no overflow)
- [ ] **R5** : Forget test passes (soft-deleted facts don't appear in searches)
- [ ] **R6** : Audit query works (facts inspectable with full metadata)
- [ ] **Judge quality** : Confidence/recall metrics computable
- [ ] **Version history** : Updates traceable
- [ ] **Error handling** : Network failures, DB timeouts handled gracefully

---

**Version** : 1.0  
**Date** : 30 juin 2026
