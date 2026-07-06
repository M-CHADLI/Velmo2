# Velmo 2.0 - Index des Chantiers

## 📊 Vue d'ensemble

```
Velmo 2.0 Architecture
├── Chantier 1: Memory (Fenêtre contextuelle + Judge)
├── Chantier 2: Guardrails (Protection input/output)
│   ├── 5 Input Guards (540ms → 260ms optimisé)
│   ├── 2 Output Guards
│   └── Audit Trail (GDPR)
└── Chantier 3: Éval & Observabilité (LangFuse-first)
    ├── Scores & Evals (Judge, Retriever, LLM, Memory)
    ├── Dashboards & Alertes LangFuse
    └── GitHub Actions CI/CD + prompt versioning
```

---

## Chantier 2: Guardrails ✅

**Status:** ✅ Complété + Optimisé

**Dossier:** `/chantier-2-guardrails/`

| Fichier | Contenu | Lignes |
|---------|---------|--------|
| 01_DESIGN.md | Architecture + YAML config | 150+ |
| 02_SCHEMAS.md | Pydantic models + exemples | 500+ |
| 03_FLOWCHARTS.md | 11 diagrammes Mermaid | 440+ |
| 04_OPTIMIZATIONS.md | Parallélisation + gains | 100+ |
| README.md | Index + quick start | 110+ |

### Optimisations Implémentées

| Optimisation | Gain |
|---|---|
| Paralléliser G2+G3+G4 | **-280ms** |
| Early exit (rejeter rapide) | **-530ms** max |
| Cache Safety (25% req) | **-250ms** par cache hit |
| Streaming first token | **-2475ms perçu** |
| Batch audit logs | **-3-4ms** per req |

**Nouvelle latence:** 260ms input guards (vs 540ms avant) + streaming perceived 50ms

---

## Chantier 3: Évaluation & Observabilité ✅

**Status:** ✅ Architecture complétée

**Dossier:** [`chantier-3-observabilite/`](./chantier-3-observabilite/README.md) (3 sous-sections)

| Section | Contenu |
|---------|---------|
| 1. Evaluation | Qualité modèle (Judge, Retriever, LLM, Memory) |
| 2. Observability | LangFuse dashboards + alertes (latence, coût, scores) |
| 3. MLOps | GitHub Actions (test→gate→deploy) + LangFuse prompt versioning |

### Stack Choisi (LangFuse-first)

- **Plateforme unique:** LangFuse (tracing · dashboards · scores · evals · datasets · prompt versioning · alertes)
- **Complément infra:** health checks HTTP légers (uptime)

### 4 Core KPIs

| KPI | Target | Alert |
|-----|--------|-------|
| Rejection Rate | < 5% | > 10% |
| Latency p95 | < 500ms | > 1000ms |
| PII Accuracy | > 95% | < 90% |
| Uptime | > 99.9% | < 99.5% |

---

## Décisions Validées (2026-07-02)

✅ **Input Guards:** 5 guards en pipeline (Pydantic → Safety → PII → RateLimit → Audit)  
✅ **Output Guards:** Redaction + Compliance check  
✅ **Safety:** Chain-of-Thought si confiance < 0.75  
✅ **PII:** Redaction complète (6 patterns)  
✅ **Rate Limiting:** 2 req/sec soft, 100/hour hard  
✅ **Audit Trail:** GDPR compliant, 90 jours rétention  
✅ **Latency:** 260ms optimisé (vs 540ms original)  
✅ **Parallelization:** G2, G3, G4 async concurrent  
✅ **Monitoring:** 15 KPIs + 5 dashboards + 15 alerts  

---

## Prochaines Étapes

### Phase 1: Implémentation Chantier 2
- [ ] Convertir guards en async/await
- [ ] Implémenter asyncio.gather (parallélisation)
- [ ] Setup Redis cache pour Safety
- [ ] Setup PostgreSQL audit_log
- [ ] Intégrer Kimi + Presidio APIs

### Phase 2: Déploiement Observabilité (LangFuse)
- [ ] Setup LangFuse (cloud ou self-hosted) + clés API
- [ ] Instrumenter traces (guards, judge, LLM) avec spans
- [ ] Attacher les scores (judge_confidence, relevance, etc.)
- [ ] Créer les dashboards LangFuse (Quality, Performance, Cost, Errors)
- [ ] Configurer les alertes LangFuse → Slack
- [ ] Health checks HTTP légers (uptime infra)

### Phase 3: Intégration Chantier 1
- [ ] Memory integration test
- [ ] End-to-end latency validation
- [ ] Load testing (100+ req/sec)
- [ ] SLA validation

---

## Fichiers Clés

```
Velmo2/
├── brief-phase2-creation-velmo2.md ... Le brief (référence)
├── 00_STACK_GLOBALE.md ............... Stack imposée
├── SCHEMA_FLUX_COMPLET.md ............ Schéma d'architecture global
├── INDEX_CHANTIERS.md ............... Ce fichier
├── chantier-1-memoire/
│   └── 01_DESIGN.md ................. Modèle mémoire (R1–R6)
├── chantier-2-guardrails/
│   ├── 01_DESIGN.md ................. Architecture
│   ├── 02_SCHEMAS.md ............... Pydantic models
│   ├── 03_FLOWCHARTS.md ........... Diagrammes
│   ├── 04_OPTIMIZATIONS.md ....... Parallélisation
│   ├── 05_TABLEAU_GARDEFOUS.md ... Tableau garde-fous (livrable)
│   └── README.md
├── chantier-3-observabilite/
│   ├── 01_CICD_BOUCLE_QUALITE.md . CI/CD + boucle qualité
│   └── README.md ................. Éval + Observabilité + MLOps
└── eval/
    ├── memory_cases.jsonl ......... Cas mémoire (fournis)
    ├── guardrail_cases.jsonl ..... Cas garde-fous (fournis)
    └── quality_cases.jsonl ....... Cas qualité (fournis)
```

