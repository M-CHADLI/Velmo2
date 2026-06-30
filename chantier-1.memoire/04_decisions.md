# Décisions — Chantier 1 : Mémoire

**Tableau récapitulatif** des choix architecturaux avec justifications et compromis.

---

## Matrice de décisions

| # | Décision | Choix | Raison | Compromis | Impact |
|----|----------|-------|--------|-----------|--------|
| **D1** | **Architecture** | 3 couches (court terme + judge + long terme) | Équilibre: granularité brute + extraction intelligente + persistance | Complexité augmente | R1, R2, R3, R4 couvertes |
| **D2** | **Fenêtre glissante** | FIFO, 100k tokens | Budget réaliste, suffisant pour 30+ tours | Messages au-delà s'effacent | R1, R4 |
| **D3** | **Cadence judge** | Tous les 10 messages | Coût maîtrisé (1 appel tous 10 msg, pas chaque msg) | Pas d'extraction continue | Latence acceptable |
| **D4** | **Modèle judge** | Même que LLM principal (Opus) | Cohérence + qualité d'extraction | Coût LLM doublement | Qualité ++ |
| **D5** | **Historique fait** | 2–3 dernières versions | Monitor qualité judge sans overload | Pas d'historique complet | R6 (traçabilité partielle) |
| **D6** | **Isolation** | Collection par user_id (1 table par user) | Simple + sûr, pas de requête cross-user accidentelle | Pas de requête globale | R3 (isolation stricte) |
| **D7** | **Suppression** | Soft-delete (marquer, ne pas effacer) | Audit trail complet + vérification possible | Pas de vrai nettoyage | R5 (droit oubli tracé) |
| **D8** | **Recherche** | Vectorielle (embedding + cosine) | Pertinence sémantique vs mots-clés | Coût embedding/tour | R4 (sélection intelligente) |
| **D9** | **Métadonnées** | confidence + source + sensitivity + pii_category | Monitoring qualité judge + garde-fous + audit | Surcharge schéma | R6 + interdépendance Chantier 2 |
| **D10** | **Embedding model** | text-embedding-3-large (ou similaire) | Standard, performant | Coût + latence | Recherche vectorielle efficace |
| **D11** | **Base vectorielle** | Pinecone / Weaviate / SQLite+pgvector | TBD selon infra | Dépendance infra | Scalabilité selon choix |
| **D12** | **Timestamp fields** | created_at, updated_at, last_accessed_at | Audit complet | Surcharge requêtes | R6 (traçabilité) |

---

## Décisions critiques (detailing)

### D1 — Architecture 3 couches

**Chosen**: Court terme (fenêtre) + Judge (extraction) + Long terme (persistant)

**Alternatives considered:**
- ❌ **Fenêtre seule** : impossible de tenir R1 (30+ tours) car fenêtre glisse
- ❌ **Persistance seule** : perd la granularité brute, tout passe par judge
- ❌ **Résumé glissant** : chaque tour résumé → perte d'info critique

**Justification:**
- Fenêtre garde le brut (granularité)
- Judge extrait intelligemment (efficacité)
- Persistance long terme (R2)

**Trade-off:** Complexité (3 systèmes à intégrer), mais non-bloquant.

---

### D2 — Budget 100k tokens

**Chosen**: 100k tokens max pour fenêtre glissante

**Calculation:**
```
Moyenne par message (user + assistant) : ~150 tokens
30 tours = 30 * 2 * 150 = 9,000 tokens
Buffer pour contexte LLM + faits injectés = ~20–30k tokens
Total avec marge : 100k tokens réaliste et sûr
```

**Alternatives:**
- 50k : trop serré, perd tours avant R1
- 200k : coûteux, moins de pression d'optimiser

**Justification:**
- Couvre 30+ tours confortablement
- Laisse espace pour faits injectés
- Coût tokens acceptable

**Trade-off:** Si conversation devient très longue (100+ tours), rotation plus agressive.

---

### D3 — Judge tous les 10 messages

**Chosen**: Extraction LLM tous les 10 messages

**Cost analysis:**
```
Scénario 1 : Judge à chaque message
  → 1 appel LLM / message = coûteux, latence ++

Scénario 2 (chosen) : Judge tous les 10 messages
  → 1 appel LLM / 10 messages = 10× moins cher
  
Scénario 3 : Judge quand fenêtre pleine
  → Imprévisible, peut être tardif
```

**Justification:**
- Équilibre coût-bénéfice
- Cadence régulière et prévisible
- 10 messages = granularité raisonnable

**Trade-off:** Pas d'extraction continue (lag de max 10 messages), acceptable.

---

### D5 — Historique limité (2–3 versions)

**Chosen**: Garder 2–3 dernières versions de chaque fait

**Alternatives:**
- Historique complet : 100% traçable, mais surcharge DB
- Pas d'historique : perds détection de changements

**Justification:**
- Monitor qualité judge (détecte mises à jour)
- Pas de surcharge DB
- Suffisant pour audit

**Trade-off:** Perd très ancien historique, acceptable pour R6.

---

### D6 — Isolation par user_id

**Chosen**: Chaque user = collection/table dédiée

**Alternatives:**
- Colonne user_id dans table unique : simpler, mais risque de bug cross-tenant
- Partition par user_id : complexe si DB ne supporte pas

**Justification:**
- Simple et sûr
- Pas d'erreur d'isolation possible
- Requête rapide (une table)

**Trade-off:** Pas de requête cross-user (mais inutil), gestion dynamique tables.

---

### D7 — Soft-delete pour R5

**Chosen**: Marquer soft_deleted + deletion_reason, ne pas effacer

**Alternatives:**
- Hard delete : simple, mais perd audit trail
- Logical delete avec shadowing : trop complexe

**Justification:**
- Traçabilité complète (R6)
- Vérification possible (test que fait ne ressort plus)
- Respect RGPD (suppression vérifiable)

**Trade-off:** DB grandit (faits morts), acceptable avec cleanup périodique.

---

### D8 — Recherche vectorielle

**Chosen**: Embedding + cosine similarity (base vectorielle)

**Alternatives:**
- Regex/mots-clés : simple, mais peu pertinent
- BM25 : meilleur que regex, mais moins sémantique
- Vectorielle : sémantique optimale

**Justification:**
- Comprend le sens (user: "ma facture" → retrouve "invoice")
- Scalable
- Moderne

**Trade-off:** Coût embedding/tour, acceptable (< 100ms).

---

### D9 — Métadonnées complètes (confidence, source, sensitivity)

**Chosen**: Garder tous les champs de contexte

**Alternatives:**
- Schéma minimal : léger, mais impossible de monitorer
- Schéma complet (chosen) : lourd, mais tout est inspectable

**Justification:**
- Monitoring Chantier 3 (détecter judge failures)
- Garde-fous Chantier 2 (savoir sensibilité)
- Audit R6

**Trade-off:** Surcharge schéma (mais JSON flexible).

---

## Validation des exigences par décision

| Exigence | Couverture | Via décisions |
|----------|-----------|----------------|
| **R1** | ✅ 100% | D1 (fenêtre + judge), D2 (100k tokens), D3 (cadence) |
| **R2** | ✅ 100% | D1 (long terme persistant) |
| **R3** | ✅ 100% | D6 (isolation par user_id) |
| **R4** | ✅ 100% | D1 (fenêtre glissante), D8 (recherche sélective) |
| **R5** | ✅ 100% | D7 (soft-delete traçable) |
| **R6** | ✅ 95% | D5 (historique limité), D9 (métadonnées) — *Minor: historique partiel* |

---

## Points ouverts (pour implémentation)

| Point | Décision | Statut |
|-------|----------|--------|
| Choix base vectorielle (Pinecone vs Weaviate vs pgvector) | À affiner selon infra | À valider |
| Modèle embedding (dimension, provider) | text-embedding-3-large (suggested) | À confirmer |
| Prompt du judge (exact wording) | À écrire dans Chantier 1 code | À définir |
| Seuil confidence pour persistance | Tous les faits (no threshold) | À tester |
| Cleanup de soft_deleted (fréquence) | À définir lors du code | À implémenter |
| Sync multi-instance (si plusieurs judge runners) | À définer dans DevOps | Hors scope pour phase 1 |

---

## Risques et mitigation

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|-----------|
| Judge hallucine / confidence faible | Moyen | Mémoire invalide | Monitoring Chantier 3 + test acceptance |
| Fenêtre pleine avant judge → infos perdues | Faible | Régression R1 | Budget 100k + monitoring fenêtre |
| Erreur isolation user_id → fuite mémoire autre user | Très faible | Critique | Validation stricte user_id + tests |
| Embedding coûteux → latence augmente | Faible | UX | Caching embeddings, optimiser modèle |
| Soft-delete → DB grandit | Moyen | Perf long terme | Plan cleanup / archivage |

---

## Dépendances vers autres chantiers

**Vers Chantier 2 (Garde-fous):**
- Champ `sensitivity` + `pii_category` dans mémoire → utilisé par garde-fous pour détecter PII
- Si fact supprimé → garde-fou sait qu'il existe

**Vers Chantier 3 (MLOps):**
- Métadonnées (confidence, source) → mesurer qualité judge
- Version history → détecter dérives de qualité
- Tests d'acceptance sur memory_cases.jsonl → valider extraction

---

## Évolutions futures (Phase 2+)

- [ ] Compression automatique de version_history > 3
- [ ] Re-embedding quand prompt judge améliore
- [ ] Prédiction proactive de faits (avant judge)
- [ ] Synthetic generation de test cases
- [ ] Apprentissage du judge (fine-tuning)

---

**Version** : 1.0  
**Date** : 30 juin 2026  
**Révisé par** : [à remplir]
