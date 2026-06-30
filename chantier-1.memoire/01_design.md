# Design — Chantier 1 : Mémoire

**Document de conception complet** du Chantier 1 (Mémoire) pour Velmo 2.0.

---

## 📋 Exigences (R1–R6)

| # | Exigence | Description | Satisfait par |
|---|----------|-------------|---------------|
| **R1** | Tenir 30+ tours | Sans perdre une info donnée au début | Fenêtre glissante + Judge |
| **R2** | Mémoire persistante | Se souvenir d'une session à l'autre | Base long terme |
| **R3** | Isolation stricte | Un utilisateur ≠ accès mémoire autre | Collection par user_id |
| **R4** | Budget tokens | Fenêtre de contexte 100k tokens | Fenêtre glissante + sélection vectorielle |
| **R5** | Droit à l'oubli | Suppression effective et vérifiable | Soft-delete + fact_id traçable |
| **R6** | Traçabilité | Inspection complète de la mémoire | Métadonnées (source, confidence, version_history) |

---

## 🏗️ Architecture — 3 couches

### Couche 1 : Mémoire court terme (fenêtre glissante)

**Contenu :**
- Messages bruts (user + assistant) de la conversation en cours
- Numérotés séquentiellement (message 1, 2, 3, ...)

**Caractéristiques :**
- **Budget** : 100k tokens max
- **Politique** : FIFO glissant (quand > 80 % du budget, les anciens tours quittent)
- **Durée de vie** : session actuelle seulement
- **Rôle** : garder la granularité brute pour le judge, données de travail pour le LLM

**Exemple :**
```
Tour 1 : User: "Bonjour, je suis Karim, numéro KX-4471"
         Assistant: "Bonjour Karim, comment puis-je vous aider ?"

Tour 2 : User: "J'ai une question sur ma facture"
         Assistant: "Je vais chercher vos factures..."

...

Tour 31 : User: "Rappelle-moi mon numéro de contrat"
          (Le tour 1 a peut-être quitté la fenêtre, mais le judge l'a capturé)
```

---

### Couche 2 : Judge agent (extraction tous les 10 messages)

**Cadence :**
- S'exécute après chaque bloc de **10 messages consécutifs**
- Coût : 1 appel LLM tous les 10 messages (maîtrisé)

**Processus :**
1. Lit les **10 messages bruts** de la fenêtre courante
2. Lit les **faits persistants existants** de l'utilisateur
3. Compare et décide :
   - Nouveaux faits à créer
   - Faits existants à mettre à jour (synchronisation)
   - Faits à confirmer/valider
4. Produit une liste de **faits structurés** avec métadonnées
5. Embedding chaque fait (pour recherche vectorielle)
6. Persiste dans la collection dédiée à l'utilisateur

**Exemple (après messages 1–10) :**
```
Input : 10 messages bruts + faits existants (vides)
Judge output :
  [
    {fact_id: "f1", key: "name", value: "Karim", type: "identifier", confidence: 0.99, source: "user_statement"},
    {fact_id: "f2", key: "contract_number", value: "KX-4471", type: "identifier", confidence: 0.99},
    {fact_id: "f3", key: "account_type", value: "pro", type: "status", confidence: 0.87, source: "extracted_from_context"}
  ]

→ Persisted
```

---

### Couche 3 : Mémoire long terme persistante

**Stockage :**
- **Base relationnelle** : faits structurés, métadonnées, historique
- **Base vectorielle** : embeddings pour recherche sémantique

**Isolation :**
- Chaque utilisateur = sa propre **collection de faits**
- Accès vérifié au niveau applicatif (user_id validation)
- Aucun croisement possible

**Recherche :**
- À chaque tour : requête vectorielle « Quels faits sont pertinents pour ce message ? »
- Top-N faits sélectionnés et injectés en haut du prompt LLM
- Score de pertinence calculé en temps réel

**Durée de vie :**
- Multi-session → R2 (se souvenir d'une session à l'autre)
- Persistent tant que l'utilisateur n'a pas demandé suppression → R5

---

## 📊 Schéma de données — Fait structuré

### Structure principale

```json
{
  "fact_id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "contract_number",
  "value": "KX-9999",
  "conversation_id": "conv_20260630_karim_001",
  
  "type": "identifier",
  "source": "user_statement",
  "confidence": 0.99,
  
  "sensitivity": "medium",
  "pii_category": "contract_id",
  
  "extracted_at_message": 1,
  "created_at": "2026-06-30T10:00:00Z",
  "updated_at": "2026-06-30T10:45:00Z",
  "last_accessed_at": "2026-06-30T11:30:00Z",
  
  "version_history": [
    {
      "version": 2,
      "value": "KX-9999",
      "message": 42,
      "timestamp": "2026-06-30T10:45:00Z",
      "reason": "user_update"
    },
    {
      "version": 1,
      "value": "KX-4471",
      "message": 1,
      "timestamp": "2026-06-30T10:00:00Z",
      "reason": "initial_extraction"
    }
  ],
  
  "status": "active",
  "deletion_reason": null,
  
  "embedding": [0.123, 0.456, 0.789, ...]
}
```

### Dictionnaire des champs

| Champ | Type | Description | Usage |
|-------|------|-------------|-------|
| `fact_id` | UUID | Identifiant unique | R5 (suppression), R6 (audit) |
| `key` | String | Clé du fait (ex. "contract_number") | Sélection et recherche |
| `value` | Any | Valeur réelle | Contexte LLM |
| `conversation_id` | String | ID de la conversation → contexte local vs durable | R2, R3 (isolation) |
| `type` | Enum | Catégorie : identifier / preference / status / context | Raisonnement judge |
| `source` | String | D'où vient le fait : user_statement / extracted_from_context / inferred | Audit, débogage |
| `confidence` | Float (0–1) | Certitude du judge | Monitoring (Chantier 3) |
| `sensitivity` | Enum | low / medium / high | Garde-fous (Chantier 2) |
| `pii_category` | String | Type PII : contract_id / payment_card / password / other | Suppression sélective (R5) |
| `extracted_at_message` | Int | Numéro du message lors de l'extraction | Traçabilité (R6) |
| `created_at` | Timestamp | Quand le fait a été créé | Audit |
| `updated_at` | Timestamp | Dernière mise à jour | Synchronisation |
| `last_accessed_at` | Timestamp | Dernier accès (pour détection stale data) | Monitoring |
| `version_history` | Array | 2–3 dernières versions (valeur + métadonnées) | Monitor qualité judge |
| `status` | Enum | active / soft_deleted | R5 (suppression traçable) |
| `deletion_reason` | String | Raison suppression (si applicable) | Audit trail (R6) |
| `embedding` | Array[Float] | Vecteur d'embedding (dim. dépend du modèle) | Recherche vectorielle |

### Types de faits

- **identifier** : informations identifiantes (nom, contrat, n° client, email)
- **preference** : préférences utilisateur (tutoyé, langue, format)
- **status** : statuts (pro/particulier, actif/suspendu)
- **context** : contexte opérationnel (ce qu'il a demandé, problème signalé)

---

## 🔄 Flux complet par tour

```
┌─────────────────────────────────────────────────────────────────┐
│ CHAQUE TOUR DE CONVERSATION                                     │
└─────────────────────────────────────────────────────────────────┘

1. MESSAGE UTILISATEUR ARRIVE
   └─ Ajouté à la fenêtre glissante (court terme)
      ├ Numérotation : message N
      └ Horodatage

2. VÉRIFIER CADENCE JUDGE
   ├─ Tous les 10 messages ?
   │  ├─ OUI → [JUDGE EXÉCUTE]
   │  │  ├ Lit les 10 messages bruts + faits persistants existants
   │  │  ├ Extrait / met à jour / synchronise
   │  │  ├ Embedding chaque fait
   │  │  └─ Persiste en base (collection user_{user_id})
   │  │
   │  └─ NON → continue
   │
   └─ Fenêtre glissante à 80 % du budget ?
      ├─ OUI → Les anciens tours quittent (FIFO)
      └─ NON → continue

3. AVANT APPEL LLM PRINCIPAL
   ├ [RECHERCHE VECTORIELLE]
   │  ├ Embed(message utilisateur) → vecteur
   │  ├ Requête base vectorielle : "Quels faits sont pertinents ?"
   │  └─ Résultats triés par score de pertinence
   │
   ├ [SÉLECTION]
   │  ├ Top-N faits (selon budget tokens disponible)
   │  └─ Filtre : status = "active" (exclure soft-deleted)
   │
   └─ [INJECTION EN PROMPT]
      └─ Emplacement : en haut du prompt
         ```
         Contexte utilisateur :
         - Nom : Karim
         - Contrat : KX-9999
         - Type : Pro
         
         Conversation :
         [derniers messages de la fenêtre]
         ```

4. APPEL LLM PRINCIPAL
   ├ Reçoit : contexte + fenêtre glissante + faits pertinents
   └─ Produit : réponse

5. RÉPONSE À L'UTILISATEUR
   └─ Stockage : réponse ajoutée à la fenêtre glissante (si espace)

[Boucle revient à l'étape 1]
```

---

## 🔐 Isolation (R3) et droit à l'oubli (R5)

### Isolation stricte (R3)

**Implémentation :**
```
Base de données relationnelle :
  Table: users_{user_id}_facts
  ├─ Contient TOUS les faits de cet utilisateur
  ├─ Clé primaire : fact_id
  └─ Index : user_id (pour requêtes rapides)

Base vectorielle :
  Namespace: {user_id}
  ├─ Tous les vecteurs d'embedding de cet utilisateur
  └─ Requête : ne traverse JAMAIS d'autres namespaces
```

**Vérifications applicatif :**
- Avant toute requête : vérifier `user_id` du token JWT/session
- Refuser l'accès si mismatch

### Droit à l'oubli (R5)

**Flux suppression :**
```
User dit : "Oublie mon numéro de contrat KX-9999"
  ↓
Agent extrait : fact_key = "contract_number", fact_value = "KX-9999"
  ↓
Recherche : SELECT * FROM users_{user_id}_facts WHERE key = "contract_number"
  ↓
Soft-delete (NE PAS effacer la ligne) :
  UPDATE users_{user_id}_facts 
  SET status = "soft_deleted", 
      deletion_reason = "user_requested_on_2026-06-30T12:00:00Z"
  WHERE fact_id = "..."
  ↓
Base vectorielle : Mettre à jour l'enregistrement (marquer supprimé)
  ↓
Vérification : Requête vectorielle suivante = filtre "status != soft_deleted"
  ↓
Réponse utilisateur : "Votre numéro de contrat a été oublié"
```

**Traçabilité (R6) :**
- `deletion_reason` reste enregistré (pour audit)
- Historique des suppressions queryable (événements)
- Chantier 3 : test que le fait ne ressort plus

---

## 🔍 Traçabilité (R6)

Tout fait doit être inspectable via un endpoint audit :

```
GET /memory/{user_id}/facts/{fact_id}
→ Retourne structure complète + version_history + deletion_reason
```

Exemple de réponse :
```json
{
  "fact_id": "550e8400...",
  "key": "contract_number",
  "value": "KX-9999",
  "source": "user_statement",
  "confidence": 0.99,
  "created_at": "2026-06-30T10:00:00Z",
  "updated_at": "2026-06-30T10:45:00Z",
  "version_history": [...],
  "status": "active",
  "deletion_reason": null,
  "_trace": {
    "extracted_at_message": 1,
    "judge_model": "claude-opus-4-8",
    "extraction_round": 1
  }
}
```

---

## 📈 Points de décision & justifications

| Décision | Choix | Raison | Compromis |
|----------|-------|--------|-----------|
| **Cadence judge** | 10 messages | Équilibre coût (1 appel) vs granularité | Pas d'extraction continue |
| **Historique fait** | 2–3 versions | Monitor qualité judge sans overload | Pas d'historique complet |
| **Fenêtre glissante** | 100k tokens | Budget réaliste pour production | Messages au-delà s'effacent si judge manque |
| **Soft-delete** | Oui (R5) | Traçabilité audit | Pas de nettoyage total |
| **Isolation** | Collection/user_id | Simple + sûr | Pas de requête cross-user accidentelle |
| **Recherche** | Vectorielle | Pertinence sémantique > mots-clés | Coût embedding à chaque tour |

---

## 🚀 Prochaines étapes

1. **Validation** : présenter ce design au formateur
2. **Développement** (jours 2–5) :
   - Implémenter couche 1 (fenêtre glissante)
   - Implémenter couche 2 (judge agent)
   - Implémenter couche 3 (persistance + recherche)
   - Tests d'acceptance (R1–R6)
3. **Chantier 2** : concevoir les garde-fous
4. **Chantier 3** : concevoir l'évaluation & MLOps

---

**Version** : 1.0 (Design)  
**Date** : 30 juin 2026  
**Statut** : En attente de validation
