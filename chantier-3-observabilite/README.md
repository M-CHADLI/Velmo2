# Chantier 3 : Évaluation & Observabilité (LangFuse-first)

**Objectif :** mesurer la qualité de Velmo et surveiller sa santé, en s'appuyant **au maximum sur LangFuse** comme plateforme unique.

**Stack :** LangFuse (tracing · dashboards · scores · evals · datasets · prompt versioning · alertes) + health checks légers pour l'infra pure.

---

## Pourquoi LangFuse-first

Une seule plateforme au lieu de 5 outils : moins de setup, moins de glue code, tout corrélé au même trace_id.

| Capacité LangFuse | Remplace |
|-------------------|----------|
| **Tracing** (latence, tokens, coût par span) | Prometheus (métriques LLM) |
| **Dashboards** (analytics natifs) | Grafana |
| **Scores** (LLM-as-judge, custom, human) | scripts d'éval |
| **Datasets + Experiments** | DVC (datasets d'éval) |
| **Prompt Management** (versioning) | MLflow (prompts) |
| **Alerts** (seuils sur métriques) | AlertManager |

⚠️ **Hors périmètre LangFuse** : uptime infra, CPU/RAM, connexions DB/Redis → health checks HTTP simples (voir §4).

---

## 1. Evaluation — Qualité via LangFuse Scores

Chaque trace reçoit des **scores** (0-1). Le Judge est évalué tous les 5 tours (10 msgs).

| Composant | Score LangFuse | Méthode | Target | Critical |
|-----------|----------------|---------|--------|----------|
| **Judge** | `judge_confidence` | extraction output | > 0.85 | < 0.80 |
| **Judge** | `hallucination` | LLM-as-judge | < 5% | > 10% |
| **Retriever** | `recall@5` | dataset annoté | > 0.8 | < 0.7 |
| **Retriever** | `ndcg` | ranking eval | > 0.85 | < 0.75 |
| **LLM** | `relevance` | LLM-as-judge | > 0.85 | < 0.75 |
| **Memory** | `staleness` | version drift | < 20% | > 30% |

```python
from langfuse import Langfuse
langfuse = Langfuse()

# Attacher un score à une trace
langfuse.score(
    trace_id=trace_id,
    name="judge_confidence",
    value=0.92,
    comment="extraction 5 tours"
)
```

**Datasets & Experiments** (remplace DVC pour l'éval) :
```python
# Créer un dataset d'éval reproductible
dataset = langfuse.create_dataset(name="judge-golden-set")
langfuse.create_dataset_item(dataset_name="judge-golden-set",
    input={"conversation": "..."}, expected_output={"facts": [...]})
# Lancer une experiment → scores comparables entre versions
```

---

## 2. Observability — Dashboards LangFuse natifs

Métriques automatiques par trace (aucun instrument custom) : latence, tokens, coût, volume.

| Métrique (LangFuse) | Target | Alert |
|---------------------|--------|-------|
| Latency p95 (end-to-end) | < 2000ms | > 3000ms |
| Cost / trace | suivi tendance | spike x2 |
| Tokens / trace | suivi tendance | — |
| Score `judge_confidence` (moy.) | > 0.85 | < 0.80 |
| Score `relevance` (moy.) | > 0.85 | < 0.75 |
| Error rate (traces en échec) | < 1% | > 1% |

**Dashboards LangFuse à créer (vues natives) :**
1. **Quality** — évolution des scores (judge, relevance, hallucination)
2. **Performance** — latence p50/p95/p99 par span (guard, judge, LLM)
3. **Cost** — coût par jour / par user / par modèle
4. **Errors** — traces en échec, exceptions, timeouts

**Alertes LangFuse (seuils natifs)** → notifications Slack/email :
| Alerte | Condition |
|--------|-----------|
| Judge confidence bas | moy. `judge_confidence` < 0.80 sur 1h |
| Latence élevée | p95 > 3000ms sur 15min |
| Coût anormal | coût horaire > x2 baseline |
| Taux d'erreur | error rate > 1% sur 15min |

---

## 3. MLOps — CI/CD GitHub Actions + LangFuse

CI/CD via **GitHub Actions**, gate qualité alimenté par les scores LangFuse.

| Aspect | Solution | Détail |
|--------|----------|--------|
| **CI/CD** | GitHub Actions | Workflow test → gate → deploy |
| **Prompt versioning** | LangFuse Prompt Management | Versions labellisées (prod/staging), rollback 1-clic |
| **Gate CI/CD** | GitHub Actions + LangFuse Scores | `judge_confidence_avg ≥ 0.85` avant deploy |
| **A/B testing** | Prompt labels + scores | Comparer 2 versions sur mêmes traces |
| **Auto-rollback** | Alertes + label prod | Repointer le label `production` sur version précédente |

### Pipeline GitHub Actions

`.github/workflows/deploy.yml` — 3 jobs enchaînés : **test → gate → deploy**.

```yaml
name: Velmo CI/CD

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt pytest langfuse
      - run: pytest --cov

  gate:                              # Gate qualité sur scores LangFuse
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install langfuse
      - name: Check LangFuse scores
        run: python scripts/check_gate.py
        env:
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
          LANGFUSE_HOST: ${{ secrets.LANGFUSE_HOST }}

  deploy:                           # Deploy uniquement si gate ✅
    needs: gate
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Promote LangFuse prompt to production
        run: python scripts/promote_prompt.py
        env:
          LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
          LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
      - name: Deploy
        run: ./deploy.sh
```

`scripts/check_gate.py` — bloque le pipeline si la qualité chute :

```python
from langfuse import Langfuse

lf = Langfuse()
traces = lf.fetch_traces(name="Velmo-2.0", from_timestamp="2024-01-01").data
confidences = [t.scores.get("judge_confidence", 0) for t in traces]
avg = sum(confidences) / len(confidences)

if avg < 0.85:
    print(f"❌ Gate échoué — judge_confidence {avg:.2f} < 0.85")
    raise SystemExit(1)          # exit ≠ 0 → GitHub Actions stoppe le deploy
print(f"✅ Gate OK — judge_confidence {avg:.2f}")
```

**Secrets GitHub à configurer** (Settings → Secrets → Actions) :
`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.

---

## 4. Santé infra (hors LangFuse)

Le seul complément nécessaire — health checks HTTP légers (pas de Prometheus/Grafana).

| Check | Cible | Fréquence |
|-------|-------|-----------|
| `/health` API | 200 OK | 30s |
| PostgreSQL | ping < 50ms | 1min |
| Redis | ping < 10ms | 1min |
| Kimi / Presidio | endpoint up | 1min |

> Uptime réel mesurable via un simple uptime-monitor (ex: UptimeRobot) si besoin. Tout le reste passe par LangFuse.

---

## Intégration

- **← Chantier 1** : traces d'extraction du Judge + scores
- **← Chantier 2** : traces des guards (spans) + logs d'audit
- **→ CD Pipeline** : gate sur scores LangFuse → deploy / rollback

---

## Variables d'environnement

```bash
# LangFuse — plateforme unique
LANGFUSE_PUBLIC_KEY=<your-public-key>
LANGFUSE_SECRET_KEY=<your-secret-key>
LANGFUSE_HOST=https://cloud.langfuse.com   # ou self-hosted
```
