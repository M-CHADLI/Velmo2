# Chantier 1 — Mémoire (Velmo 2.0)

**Statut** : Design en validation (session du 30 juin 2026)

Index de la documentation du Chantier 1 (Mémoire). Tous les fichiers ci-dessous constituent le **design doc complet** validé avant développement.

---

## 📚 Structure du dossier

```
chantier-1.memoire/
├── README.md (ce fichier — index)
├── 01_design.md (design doc complet : exigences, architecture, décisions)
├── 02_schemas.md (JSON Schema formel + ER diagram)
├── 03_diagrammes.md (diagrammes Mermaid : architecture, flux)
├── 04_decisions.md (tableau récapitulatif des choix)
├── 05_cas-usage.md (scénarios concrets de test)
├── /schemas/ (fichiers JSON Schema)
│   ├── facts.schema.json
│   └── extraction_metadata.schema.json
├── /diagrams/ (diagrammes Mermaid exportables)
│   ├── architecture.mermaid
│   ├── flux-par-tour.mermaid
│   └── entity-relationship.mermaid
└── /code/ (vide, à remplir au développement)
```

---

## 🎯 Lecture recommandée

**Pour comprendre le design :**
1. Commencer par [**01_design.md**](01_design.md) — contexte complet
2. Consulter [**03_diagrammes.md**](03_diagrammes.md) — visualisations
3. Vérifier [**04_decisions.md**](04_decisions.md) — justifications des choix

**Pour développer :**
1. [**02_schemas.md**](02_schemas.md) — schémas de données formels
2. [**05_cas-usage.md**](05_cas-usage.md) — cas de test pour validation
3. `/schemas/` et `/diagrams/` — spécifications techniques

---

## 📋 Résumé exécutif

**Architecture à 3 couches :**

| Couche | Nom | Budget | Durée | Rôle |
|--------|-----|--------|-------|------|
| 1 | Fenêtre glissante (court terme) | 100k tokens | Session actuelle | Granularité brute, données de travail |
| 2 | Judge agent | 1 appel / 10 msgs | Pendant la session | Extraction et synchronisation des faits |
| 3 | Base persistante + vectorielle | Illimité | Multi-session | Mémoire long terme, recherche sémantique |

**Clés du design :**
- ✅ R1 : Tenir 30+ tours (fenêtre + judge)
- ✅ R2 : Mémoire long terme persistante
- ✅ R3 : Isolation stricte par user_id
- ✅ R4 : Budget de contexte (100k tokens)
- ✅ R5 : Droit à l'oubli (soft-delete traçable)
- ✅ R6 : Traçabilité complète (metadata)

**Schéma de faits :**
```json
{
  "fact_id": "uuid",
  "key": "contract_number",
  "value": "KX-9999",
  "type": "identifier",
  "source": "user_statement",
  "confidence": 0.99,
  "sensitivity": "medium",
  "version_history": [2-3 dernières versions],
  "status": "active | soft_deleted"
}
```

---

## 🔄 Flux principal par tour

```
Message utilisateur
  ↓
Ajout fenêtre glissante (court terme)
  ↓
Tous les 10 messages ?
  ├─ OUI → Judge extrait + synchronise faits
  └─ NON → continue
  ↓
Recherche vectorielle (faits pertinents)
  ↓
Injection faits dans prompt LLM
  ↓
LLM répond
  ↓
Réponse utilisateur
```

Voir [**03_diagrammes.md**](03_diagrammes.md) pour la visualisation complète.

---

## 🛠️ Développement

Le dossier `/code/` sera rempli pendant les jours 2–5 avec :
- Implémentation mémoire court terme
- Judge agent
- Persistance et isolation
- Droit à l'oubli
- Tests d'acceptance

Structure proposée (à affiner) :
```
/code/
├── short_term_memory.py (ou .ts/.js)
├── judge_agent.py
├── persistent_storage.py (ou .sql/.json)
├── vector_db.py
├── memory_utils.py
└── tests/
    └── test_memory_acceptance.py
```

---

## 📞 Points de contact

**Questions sur le design ?**
- Design doc complet : [01_design.md](01_design.md)
- Schémas formels : [02_schemas.md](02_schemas.md)
- Justifications : [04_decisions.md](04_decisions.md)

**Prêt à développer ?**
- Cas d'usage : [05_cas-usage.md](05_cas-usage.md)
- Diagrammes : [03_diagrammes.md](03_diagrammes.md)
- Structures : `/schemas/*.schema.json`

---

**Validé par** : [à remplir après validation formateur]  
**Date** : 30 juin 2026  
**Version** : 1.0 (design)
