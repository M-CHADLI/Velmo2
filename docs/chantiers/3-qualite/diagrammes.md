[📖 Documentation](../../README.md) › [Chantier 3](README.md) › Diagrammes

# 🖼️ Chantier 3 — Diagrammes

Trois vues visuelles pour tout comprendre : ce qui se passe **quand on lance
l'évaluation**, comment ça s'articule **dans la CI**, et **comment le gate décide**.

## 1. Séquence — que fait `run_eval.py`

C'est le déroulé d'un `make quality` (ou d'un run CI).

```mermaid
sequenceDiagram
    autonumber
    participant Dev as 👤 Dev / CI
    participant RE as mlops/run_eval.py
    participant MEM as Suite Mémoire
    participant GF as Suite Garde-fous
    participant QA as Suite Qualité
    participant FS as 📄 Fichiers

    Dev->>RE: lance l'évaluation
    RE->>MEM: rejoue 12 cas (rappel, isolation, oubli)
    MEM-->>RE: taux de réussite (ex. 100%)
    RE->>GF: rejoue 37 cas (toxiques + légitimes)
    GF-->>RE: taux de réussite + block_rate + faux positifs
    RE->>QA: rejoue 8 cas (questions support)
    QA-->>RE: taux de réussite (ex. 75%)

    RE->>RE: note globale = 40% mémoire<br/>+ 40% garde-fous + 20% qualité
    RE->>FS: écrit report.md + ajoute 1 ligne à history.jsonl

    alt note ≥ 70
        RE-->>Dev: affiche [OK] et sort avec le code 0 ✅
    else note < 70
        RE-->>Dev: affiche [ECHEC] et sort avec le code 1 ❌
    end
```

## 2. Flux CI — deux workflows complémentaires

Le projet a **deux** workflows GitHub Actions, qui ne font pas la même chose :

```mermaid
flowchart TB
    subgraph CI["ci.yml — automatique, gratuit"]
        direction TB
        P([Push / Pull Request]) --> L[ruff : lint] --> T[pytest : 140+ tests mockés]
    end

    subgraph QUAL["quality.yml — manuel, appelle le vrai LLM"]
        direction TB
        M([Run workflow à la main]) --> CO[checkout + install]
        CO --> ENV["écrit .env<br/>depuis le secret VELMO2"]
        ENV --> DB[init schéma + seed base]
        DB --> EV["run_eval.py<br/>(les 3 suites)"]
        EV --> GATE{note ≥ 70 ?}
        GATE -->|oui| PASS["✅ succès + rapport en artifact"]
        GATE -->|non| FAIL["❌ échec (bloque)"]
    end
```

| | `ci.yml` | `quality.yml` |
|---|----------|---------------|
| **Quand** | À chaque push / PR (automatique) | À la demande (bouton « Run workflow ») |
| **Coût** | Gratuit (LLM **mocké**) | Quelques centimes (**vrais** appels LLM) |
| **Vérifie** | Le code compile, le style, les tests unitaires | La **qualité de l'agent** (non-régression) |

👉 Les concepts (workflow, job, secret, artifact…) sont expliqués dans
[CI/CD](ci-cd.md).

## 3. Décision du gate (blocage de la livraison)

Le **gate** (« portail ») correspond au code de sortie du script. GitHub Actions
considère qu'un job **échoue** dès que la commande renvoie un code différent de 0.

```mermaid
flowchart TB
    N["Note globale calculée"] --> Q{"Note ≥ seuil (70) ?"}
    Q -->|OUI| Z["exit 0<br/>🟢 Le job réussit<br/>→ on peut livrer"]
    Q -->|NON| U["exit 1<br/>🔴 Le job échoue<br/>→ livraison bloquée"]
```

En pratique : une commande qui renvoie `1` fait échouer la CI, ce qui empêche de
merger ou de livrer.

---

**Voir aussi :** [Notation (le calcul de la note)](notation.md) ·
[CI/CD](ci-cd.md) · [Vue d'ensemble](README.md)

⬆ [Retour à l'index](../../README.md)
