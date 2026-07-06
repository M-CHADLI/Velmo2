# Chantier 3 — CI/CD & Boucle Qualité

Conception alignée sur le brief : **prouver la non-régression à chaque version**.

## Décisions validées

| Choix | Décision | Justification |
|-------|----------|---------------|
| **Stratégie Git** | GitHub Flow (`feature/*` → PR → `main` protégée) | 1 barrière PR, colle au test « régression bloque la livraison » |
| **CI** | GitHub Actions (`quality.yml`) | Imposé par le brief |
| **Environnements** | Configs, pas serveurs : `config/dev.yaml` + `config/prod.yaml` | Seuils différents, sans déploiement multi-env inutile |

---

## 1. Schéma CI/CD (déclencheurs Git)

```mermaid
flowchart TD
    subgraph DEV["🖥️ DEV — local (config/dev.yaml)"]
        A["👨‍💻 Développeur<br/>crée feature/judge-v2"] --> B["git push"]
        B --> C["⚙️ GitHub Actions<br/>seuil permissif 0.70"]
        C --> C1["lint + tests + éval rapide"]
    end

    C1 --> D["📬 Ouvre PR → main"]

    subgraph BARRIERE["🚧 BARRIÈRE — PR (config/prod.yaml, seuil 0.85)"]
        D --> E["⚙️ GitHub Actions : quality.yml"]
        E --> L["🎨 lint (ruff)"]
        E --> U["🧪 pytest (unitaires)"]
        E --> M["🧠 éval mémoire<br/>rejoue memory_cases.jsonl"]
        E --> G["🛡️ éval garde-fous<br/>rejoue guardrail_cases.jsonl"]
        E --> Q["⭐ éval qualité"]

        M --> NM["note_mem"]
        G --> NG["taux_blocage + faux_positifs"]
        Q --> NQ["note_qualité"]

        NM --> NOTE["📊 note_globale<br/>(moyenne pondérée)"]
        NG --> NOTE
        NQ --> NOTE

        NOTE --> GATE{"note_globale<br/>≥ 0.85 ?"}
    end

    GATE -->|❌ Non| BLOCK["🔴 exit 1<br/>merge bloqué"]
    GATE -->|✅ Oui| REVIEW["👀 review humaine"]

    REVIEW --> MERGE["🔀 merge → main"]

    subgraph SCEAU["🏷️ SCEAU — push sur main"]
        MERGE --> R["📝 écrit mlops/report.md"]
        R --> T["🏷️ tag version + archive note"]
    end

    BLOCK -.->|corriger| A

    style DEV fill:#e1f5ff
    style BARRIERE fill:#fff9c4
    style SCEAU fill:#c8e6c9
    style GATE fill:#ffe082
    style BLOCK fill:#ffcdd2
    style NOTE fill:#d1c4e9
```

---

## 2. Schéma « Boucle Qualité » (exigé par le brief)

> Suites d'évaluation → CI (seuil bloquant) → versionnage → signaux de suivi → retour.

```mermaid
flowchart LR
    subgraph SUITES["1️⃣ Suites d'évaluation"]
        S1["🧠 memory_cases.jsonl"]
        S2["🛡️ guardrail_cases.jsonl"]
        S3["⭐ quality set"]
    end

    subgraph SCORE["2️⃣ Notation"]
        N1["note_mem"]
        N2["note_gardefous<br/>(blocage + faux positifs)"]
        N3["note_qualité"]
        NG["📊 NOTE GLOBALE<br/>pondérée"]
    end

    subgraph CI["3️⃣ CI — quality.yml"]
        GATE{"note ≥ seuil<br/>(prod.yaml) ?"}
        PASS["✅ livraison autorisée"]
        FAIL["❌ livraison bloquée"]
    end

    subgraph VERSION["4️⃣ Versionnage"]
        V["🏷️ version = prompt<br/>+ config mémoire<br/>+ config garde-fous"]
        REP["📝 mlops/report.md<br/>(note archivée)"]
    end

    subgraph SUIVI["5️⃣ Signaux de suivi"]
        MON["note mémoire · taux blocage<br/>faux positifs · latence · coût/conv"]
    end

    S1 --> N1
    S2 --> N2
    S3 --> N3
    N1 --> NG
    N2 --> NG
    N3 --> NG

    NG --> GATE
    GATE -->|oui| PASS
    GATE -->|non| FAIL

    PASS --> V
    V --> REP
    REP --> MON
    MON -.->|dérive détectée| SUITES
    FAIL -.->|corriger| SUITES

    style SUITES fill:#e1f5ff
    style SCORE fill:#d1c4e9
    style CI fill:#fff9c4
    style VERSION fill:#c8e6c9
    style SUIVI fill:#ffe0b2
    style FAIL fill:#ffcdd2
    style PASS fill:#c8e6c9
```

---

## 3. `quality.yml` (GitHub Actions)

```yaml
name: quality

on:
  pull_request:            # BARRIÈRE — attrape la régression avant main
    branches: [main]
  push:                    # SCEAU — fige la version notée
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    env:
      # PR → prod.yaml (strict) ; push feature → dev.yaml (permissif)
      VELMO_CONFIG: ${{ github.event_name == 'pull_request' && 'config/prod.yaml' || 'config/dev.yaml' }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt ruff pytest

      - name: Lint
        run: ruff check .

      - name: Tests unitaires
        run: pytest --cov

      - name: Éval + note globale (bloque sous le seuil)
        run: python -m mlops.run_eval --config $VELMO_CONFIG

  seal:                    # uniquement après merge sur main
    needs: quality
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - name: Écrit le rapport + tag
        run: python -m mlops.write_report
```

`mlops/run_eval.py` (cœur du gate) :

```python
import sys, yaml
from mlops.suites import eval_memory, eval_guardrails, eval_quality

def main(config_path: str):
    cfg = yaml.safe_load(open(config_path))
    seuil = cfg["seuil_note_globale"]

    note_mem  = eval_memory("eval/memory_cases.jsonl")
    note_gf   = eval_guardrails("eval/guardrail_cases.jsonl",
                                fp_max=cfg["guardrails"]["faux_positifs_max"])
    note_qual = eval_quality()

    # Note globale pondérée (mémoire et garde-fous prioritaires)
    note_globale = 0.4 * note_mem + 0.4 * note_gf + 0.2 * note_qual
    print(f"note_globale = {note_globale:.3f} (seuil {seuil})")

    if note_globale < seuil:
        print("❌ Régression — livraison bloquée")
        sys.exit(1)                       # exit ≠ 0 → GitHub Actions bloque
    print("✅ Livraison autorisée")
```

---

## 4. Structure de fichiers

```
velmo-v2/
├── config/
│   ├── dev.yaml            # seuil 0.70, faux_positifs_max 0.10
│   └── prod.yaml           # seuil 0.85, faux_positifs_max 0.03
├── eval/
│   ├── memory_cases.jsonl        # fourni par le brief
│   └── guardrail_cases.jsonl     # fourni par le brief
├── mlops/
│   ├── suites.py           # eval_memory / eval_guardrails / eval_quality
│   ├── run_eval.py         # note globale + gate
│   ├── write_report.py     # génère report.md + tag
│   └── report.md           # note mémoire, blocage, faux positifs, latence, coût
└── .github/workflows/
    └── quality.yml
```

---

## 5. `config/*.yaml`

```yaml
# config/prod.yaml — strict, protège la livraison
seuil_note_globale: 0.85
guardrails:
  faux_positifs_max: 0.03

# config/dev.yaml — permissif, on itère
seuil_note_globale: 0.70
guardrails:
  faux_positifs_max: 0.10
```

---

## 6. Traçabilité de version — `mlops/report.md` (généré)

Une **version** = `prompt + config mémoire + config garde-fous`. Chaque merge archive :

| Version | note_globale | note_mem | taux_blocage | faux_positifs | latence_p95 | coût/conv |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|
| v1.2.0 | 0.89 | 0.92 | 0.98 | 0.02 | 1850ms | $0.0004 |
| v1.1.0 | 0.86 | 0.88 | 0.97 | 0.03 | 1790ms | $0.0004 |

> Les 5 signaux de suivi exigés par le brief figurent dans chaque ligne. Comparaison directe version à version = preuve de non-régression.

---

## Notes de soutenance

- **GitHub Actions ≠ stratégie Git** : GitHub Actions exécute la CI ; GitHub Flow décrit les branches. Les deux travaillent ensemble.
- **La PR est la barrière**, le push sur main est le sceau. Le test « régression bloque la livraison » se joue sur la PR.
- **Environnements = configs** (`dev.yaml`/`prod.yaml`), pas 3 serveurs : on prouve la non-régression, on ne livre pas en multi-env.
- **Note globale pondérée** (40 % mémoire, 40 % garde-fous, 20 % qualité) : mémoire et sécurité priment, conforme aux 3 exigences non négociables du brief.
- **Anti-bruit** : le seuil porte sur la note *globale* agrégée, pas sur un cas isolé → un cas qui flotte ne bloque pas seul la PR.
