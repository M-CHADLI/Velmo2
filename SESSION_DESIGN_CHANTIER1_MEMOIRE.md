# Design — Chantier 1 : Mémoire (Velmo 2.0)

**Session du 30 juin 2026** — Conception collaborative de l'architecture mémoire pour le Chantier 1 (Mémoire) de Velmo 2.0.

---

## Résumé exécutif

L'équipe a conçu une architecture mémoire à **trois couches** qui répond aux 6 exigences (R1–R6) :

1. **Mémoire court terme** : fenêtre glissante avec budget de 100k tokens (messages bruts)
2. **Mémoire intermédiaire** : judge agent qui extrait les faits tous les 10 messages
3. **Mémoire long terme persistante** : base vectorielle par utilisateur, recherche sémantique à chaque tour

Cette architecture accepte un **compromis contrôlé** : on n'Archive pas les messages bruts au-delà de la fenêtre, on fait confiance au judge et on monitore sa qualité en Chantier 3.

---

## Exigences (R1–R6)

| # | Exigence | Statut |
|---|----------|--------|
| R1 | Tenir le fil d'une conversation de 30+ tours sans perdre une info du début | ✓ Court terme (fenêtre) + long terme (judge) |
| R2 | Se souvenir d'une session à l'autre des faits durables | ✓ Base persistante + isolation par user |
| R3 | Isolation stricte par utilisateur | ✓ Collection dédiée par user_id |
| R4 | Tenir le budget de contexte (100k tokens) | ✓ Fenêtre glissante + sélection vectorielle |
| R5 | Droit à l'oubli (RGPD) | ✓ Soft-delete + fact_id traçable |
| R6 | Traçabilité (inspection) | ✓ Métadonnées complètes + historique |

---

## Architecture mémoire en trois couches

### Couche 1 : Mémoire court terme (fenêtre glissante)
- **Contenu** : messages bruts (user + assistant) de la conversation courante
- **Budget** : 100k tokens max
- **Politique** : FIFO glissant — quand le budget atteint 80 %, les plus anciens tours quittent
- **Durée de vie** : session actuelle seulement
- **Rôle** : garder la granularité brute pour le judge

### Couche 2 : Judge agent (tous les 10 messages)
- **Déclenchement** : après chaque bloc de 10 messages
- **Entrée** : les 10 messages bruts + faits existants en persistent
- **Tâche** : 
  - Extraire les faits structurés pertinents
  - Comparer avec les faits précédents
  - Mettre à jour/créer/confirmer (sync)
- **Sortie** : liste de faits typés avec métadonnées
- **Coût** : un appel LLM tous les 10 messages (coût maîtrisé)

### Couche 3 : Mémoire long terme persistante
- **Contenu** : faits structurés (voir schéma ci-dessous)
- **Stockage** : base relationnelle + base vectorielle
- **Isolation** : collection dédiée par `user_id`
- **Durée de vie** : multi-session (R2)
- **Recherche** : vectorielle à chaque tour (voir flux ci-dessous)

---

## Schéma de données — Faits persistants

### Structure principale

```json
{
  "user_id": "karim_123",
  "facts": [
    {
      "fact_id": "fact_abc123",
      "key": "contract_number",
      "value": "KX-4471",
      "type": "identifier",
      "source": "user_statement",
      "confidence": 0.99,
      "extracted_at_message": 1,
      "created_at": "2026-06-30T10:00:00Z",
      "updated_at": "2026-06-30T10:00:00Z",
      "status": "active",
      "deletion_reason": null,
      "embedding": [0.123, 0.456, ...]
    },
    {
      "fact_id": "fact_def456",
      "key": "account_type",
      "value": "pro",
      "type": "status",
      "source": "extracted_from_context",
      "confidence": 0.87,
      "extracted_at_message": 8,
      "created_at": "2026-06-30T10:15:00Z",
      "updated_at": "2026-06-30T10:15:00Z",
      "status": "active",
      "deletion_reason": null,
      "embedding": [0.789, 0.101, ...]
    }
  ],
  "extraction_metadata": {
    "extraction_id": "extract_round_001",
    "round_number": 1,
    "messages_analyzed": 10,
    "judge_model": "claude-opus-4-8",
    "created_at": "2026-06-30T10:20:00Z"
  }
}
```

### Types de faits

- `identifier` : informations identifiantes (nom, contrat, n° client)
- `preference` : préférences utilisateur (tutoyé, langue, format)
- `status` : statuts (pro/particulier, actif/suspendu)
- `context` : contexte opérationnel (ce qu'il a demandé dans cette conversation)

### Métadonnées critiques

| Champ | Rôle |
|-------|------|
| `fact_id` | Identifiant unique — pour suppression (R5) |
| `source` | D'où vient le fait — audit et débogage |
| `confidence` | 0–1 : certitude du judge |
| `extracted_at_message` | Traçabilité (R6) |
| `status` | `active` ou `soft_deleted` (R5) |
| `deletion_reason` | Audit trail si supprimé |
| `embedding` | Vecteur pour recherche sémantique |

---

## Flux par tour

```
1. MESSAGE UTILISATEUR ARRIVE
   └─ Ajouté à la fenêtre glissante (court terme)

2. TOUS LES 10 MESSAGES ?
   ├─ OUI :
   │  ├ Judge lit 10 messages + faits persistants existants
   │  ├ Extrait/met à jour les faits structurés
   │  ├ Embedding chaque fait
   │  └─ Persiste dans collection user_{user_id}
   │
   └─ NON : continue

3. AVANT APPEL LLM PRINCIPAL
   ├ Requête vectorielle : "Quels faits pertinents pour ce message ?"
   ├ Résultats triés par score de pertinence
   └─ Injecte top-N faits en haut du prompt

4. LLM PRINCIPAL RÉPOND
   └─ Référence les faits injectés

5. RÉPONSE À L'UTILISATEUR
```

---

## Stockage — Architecture multi-tenant

### Base de données relationnelle
```sql
Database: velmo_memory

Table: users_{user_id}_facts
  fact_id (PK)
  key
  value (TEXT)
  type
  source
  confidence (FLOAT)
  extracted_at_message (INT)
  created_at (TIMESTAMP)
  updated_at (TIMESTAMP)
  status (active | soft_deleted)
  deletion_reason (TEXT, nullable)
  user_id (indexed)

Table: users_{user_id}_extraction_metadata
  extraction_id (PK)
  round_number (INT)
  messages_analyzed (INT)
  judge_model (STRING)
  created_at (TIMESTAMP)
```

### Base vectorielle (Pinecone, Weaviate, SQLite+pgvector, etc.)
```
Namespace/Index: {user_id}
  ├─ Vecteur : embedding du fait
  ├─ Métadonnées : fact_id, key, value, type, status
  └─ Requête à chaque tour : embed(message) → top-5 faits
```

---

## Isolation (R3) et droit à l'oubli (R5)

### Isolation stricte (R3)
- Chaque utilisateur = sa propre collection de faits
- Accès bloqué au niveau applicatif (vérif `user_id`)
- Aucun croisement possible même en cas de bug

### Droit à l'oubli (R5)
- **Suppression** : user demande « oublie mon contrat »
- **Implémentation** : soft-delete (marquer `status = "soft_deleted"` + `deletion_reason`)
- **Vérification** : 
  - Fact n'est plus retourné par recherche vectorielle (filtre `status = active`)
  - Historique conservé pour audit (R6)
  - Chantier 3 : test que le fait n'est plus accessible

---

## Traçabilité (R6)

Tout fait est inspectable via :
1. **fact_id** : identifiant unique
2. **source** : d'où vient l'extraction
3. **confidence** : à quel point le judge était sûr
4. **extracted_at_message** : à quel moment de la conversation
5. **created_at / updated_at** : historique des mises à jour
6. **deletion_reason** : si supprimé, pourquoi et quand

**Inspection** : endpoint `/memory/{user_id}/facts?fact_id=X` pour auditer n'importe quel fait.

---

## Points de décision & compromis

### Compromis accepté
**Les messages bruts au-delà de la fenêtre ne sont pas archivés.**
- Raison : budget de tokens limité, pas d'espace disque infini
- Mitigation : le judge extrait les infos critiques avant qu'elles ne disparaissent
- Monitoring : Chantier 3 détectera si le judge rate quelque chose (score mémoire bas)

### Confiance au judge
- On accepte que le judge ne capture pas 100 % de la granularité brute
- En échange : coût maîtrisé (1 appel tous les 10 messages, pas à chaque tour)
- Validation : monitoring continu en production

---

## Points ouverts pour le développement

1. **Choix de base vectorielle** : Pinecone ? Weaviate ? SQLite+pgvector ? Dépend de l'infra.
2. **Modèle d'embedding** : quel model pour vectoriser les faits ? (ex. `text-embedding-3-large`)
3. **Seuil de confiance** : si le judge dit confidence < 0.7, stocke-t-on le fait ? Validation utilisateur ?
4. **Format du prompt injecté** : comment présenter les faits au LLM ? "Faits retenus : key=value, ..." ?
5. **Versioning du judge** : quand on améliore le judge, comment on re-traite les vieilles conversations ?

---

## Prochaines étapes

1. **Validation du schéma** : poser ce design au formateur
2. **Chantier 2** : concevoir les garde-fous (entrée/sortie)
3. **Chantier 3** : concevoir l'évaluation & MLOps (tests du judge, monitoring)
4. **Développement (Jours 2–5)** : implémenter les trois chantiers

---

**Participants** : Vous (utilisateur), Claude (assistant)  
**Date** : 30 juin 2026  
**Status** : Conception en cours — validation formateur requise
