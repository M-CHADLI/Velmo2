# 📦 Documentation historique (legacy)

> ## ⚠️ OBSOLÈTE — NE PAS UTILISER COMME RÉFÉRENCE
>
> Ce dossier contient la documentation produite pendant la phase de conception
> initiale (« vibe coding »). **Une grande partie décrit des designs qui n'ont
> jamais été implémentés** — notamment :
> - **Chantier 3** documenté ici en « LangFuse-first » (dashboards LangFuse,
>   `check_gate.py`, `promote_prompt.py`, `deploy.yml`). **Le code réel utilise
>   LangSmith + `mlops/run_eval.py` + `quality.yml`.**
> - Garde-fous mentionnant Presidio / Redis rate-limiting : **pas dans le code**.
> - KPIs, latences et pipelines cités comme cibles jamais mesurées.
>
> **Pour la documentation à jour et fidèle au code, allez au hub :
> [📖 Documentation Velmo2](../README.md).**

Ces fichiers sont conservés uniquement pour retracer l'évolution des idées.
Ils ne sont pas maintenus.

## Correspondance ancien → nouveau

| Sujet | Ancien (ici, obsolète) | Nouveau (à jour) |
|-------|------------------------|------------------|
| Vue d'ensemble | `INDEX_CHANTIERS.md`, `DEBRIEF_COMPLET.md` | [docs/README.md](../README.md) |
| Architecture globale | `SCHEMA_FLUX_COMPLET.md`, `00_STACK_GLOBALE.md` | [docs/architecture.md](../architecture.md) |
| Chantier 1 — Mémoire | `chantier-1-memoire/` | [docs/chantiers/1-memoire/](../chantiers/1-memoire/README.md) |
| Chantier 2 — Garde-fous | `chantier-2-guardrails/` | [docs/chantiers/2-guardrails/](../chantiers/2-guardrails/README.md) |
| Chantier 3 — Qualité | `chantier-3-observabilite/` | [docs/chantiers/3-qualite/](../chantiers/3-qualite/README.md) |
