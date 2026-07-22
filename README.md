# Velmo 2.0 — Agent de support client IA

Agent d'assistance client avec **mémoire persistante**, **garde-fous de sécurité**,
**boucle qualité mesurée** (CI/CD) et interfaces web / SMS / WhatsApp.
Projet d'exercice au niveau d'exigence « produit » : structure `src/` standard, tests, CI.

## 📖 Documentation

**Toute la documentation est centralisée dans le hub :**

### 👉 **[docs/README.md](docs/README.md)**

| Vous cherchez… | Allez voir |
|----------------|-----------|
| La vue d'ensemble + le schéma du flux | [docs/architecture.md](docs/architecture.md) |
| Comment l'agent se souvient | [Chantier 1 — Mémoire](docs/chantiers/1-memoire/README.md) |
| Comment l'agent bloque les contenus interdits | [Chantier 2 — Garde-fous](docs/chantiers/2-guardrails/README.md) |
| Comment on prouve la non-régression (CI/CD expliquée) | [Chantier 3 — Qualité ⭐](docs/chantiers/3-qualite/README.md) |

## 🚀 Démarrage rapide (5 min)

**Prérequis :** Python ≥ 3.11 · [uv](https://docs.astral.sh/uv/) · Docker Desktop (PostgreSQL + Redis)

```bash
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2
make setup        # install deps + Docker (PG + Redis) + init BD + seed
make streamlit    # → http://localhost:8501
```

### Configuration

Copier `.env.example` vers `.env` et renseigner au minimum :
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- `DATABASE_URL` (défaut : `postgresql://postgres:postgres@localhost:5432/velmo`)
- (optionnel) `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` pour le tracing

## 🛠️ Commandes utiles

```bash
make help         # liste complète
make streamlit    # UI web (port 8501)
make sms-server   # webhooks SMS + WhatsApp (port 8000)
make test         # pytest (140+ tests)
make lint         # ruff
make quality      # boucle qualité : 3 suites d'éval → note globale → mlops/report.md
```

## ✅ Qualité & CI

- `ci.yml` — lint + tests à chaque push (gratuit, mocké).
- `quality.yml` — boucle qualité complète, déclenchée manuellement.

Tout est expliqué (avec diagrammes, pour débutants) dans le
**[Chantier 3 — Qualité & CI/CD](docs/chantiers/3-qualite/README.md)**.

## Licence

MIT
