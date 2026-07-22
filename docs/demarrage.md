[📖 Documentation](README.md) › Démarrage

# 🚀 Démarrage — installer et lancer le projet

Guide pas à pas pour partir de zéro et obtenir Velmo 2.0 fonctionnel en local.
Chaque étape indique **la commande** et **ce que vous devez voir**.

## Prérequis

| Outil | Rôle | Installation |
|-------|------|--------------|
| **Python ≥ 3.11** | Exécuter le code | [python.org](https://www.python.org/downloads/) |
| **uv** | Gérer les dépendances (jamais `pip`) | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| **Docker Desktop** | PostgreSQL + Redis en local | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Git** | Cloner le dépôt | [git-scm.com](https://git-scm.com/) |

Il faut aussi un accès **Azure OpenAI** (une ressource Azure AI Foundry) avec :
- un modèle de **chat** déployé (ex. `gpt-5.4-mini`) ;
- un modèle d'**embedding** déployé (`text-embedding-3-small`) — indispensable à la mémoire long terme.

---

## Option express (tout-en-un)

```bash
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2
make setup        # install + Docker (PostgreSQL/Redis) + schéma DB
# → renseignez ensuite votre .env (voir étape 4), puis :
uv run python scripts/seed_business_db.py   # données fictives
make streamlit    # http://localhost:8501
```

Le détail de chaque étape suit ci-dessous.

---

## Étape par étape

### 1. Cloner le dépôt
```bash
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2
```

### 2. Installer les dépendances
```bash
UV_LINK_MODE=copy uv sync
```
- **`UV_LINK_MODE=copy`** est nécessaire ici (dossier synchronisé OneDrive) pour éviter les erreurs de lien.
- **À voir** : `uv` installe les paquets puis `+ velmo2==0.1.0` (le projet en editable).

### 3. Lancer les services Docker (PostgreSQL + Redis)
```bash
make docker-up     # = docker-compose up -d
```
- **À voir** : `✓ Services running` — PostgreSQL sur `localhost:5432`, Redis sur `localhost:6379`.
- Vérifier : `docker compose ps` doit lister les conteneurs « Up ».

### 4. Configurer les variables d'environnement
```bash
cp .env.example .env
```
Puis ouvrez `.env` et renseignez **au minimum** :
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/velmo
AZURE_OPENAI_API_KEY=<votre-clé>
AZURE_OPENAI_ENDPOINT=https://<votre-ressource>.services.ai.azure.com/openai/v1
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.4-mini
AZURE_OPENAI_API_VERSION=2025-08-07
EMBEDDING_MODEL=text-embedding-3-small
```
- L'`ENDPOINT` doit se terminer par **`/openai/v1`** (endpoint OpenAI-compatible d'Azure AI Foundry).
- `.env` n'est **jamais** commité (il est dans `.gitignore`).

### 5. Initialiser le schéma de la base
```bash
make db-init
```
- Crée toutes les tables (mémoire, garde-fous, métier). Idempotent (ré-exécutable sans risque).
- **À voir** : `✓ Database initialized`.

### 6. Peupler la base métier fictive (seed)
```bash
uv run python scripts/seed_business_db.py
```
- Génère des clients, produits et commandes fictifs (pour que l'agent ait des données à consulter).
- **À voir** : `Seed terminé : N clients, N produits, N commandes.`

### 7. Vérifier que tout marche (tests)
```bash
make test
```
- **À voir** : `... passed` (la suite complète au vert).

### 8. Lancer l'application
```bash
make streamlit     # interface web → http://localhost:8501
```
Alternatives :
```bash
uv run python scripts/velmo_cli.py    # chat en terminal
make sms-server                        # webhooks SMS + WhatsApp (port 8000)
```

---

## Et après ?

- Comprendre le système : [Architecture](architecture.md)
- Les 3 chantiers : [Mémoire](chantiers/1-memoire/README.md) · [Garde-fous](chantiers/2-guardrails/README.md) · [Qualité & CI/CD](chantiers/3-qualite/README.md)
- Lancer la boucle qualité : `make quality` (voir [Chantier 3](chantiers/3-qualite/README.md))

---

## Dépannage (problèmes courants)

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| `Access denied` / erreur de lien pendant `uv sync` | Verrou OneDrive, ou app encore lancée | Fermer streamlit/sms-server, puis `UV_LINK_MODE=copy uv sync` |
| `could not connect` à la base | Docker pas démarré | `make docker-up`, vérifier `docker compose ps` |
| L'agent ne retrouve rien en mémoire (note mémoire basse) | Modèle d'embedding **non déployé** sur Azure → embeddings « mock » | Déployer `text-embedding-3-small` sur la ressource Azure (voir [Chantier 1](chantiers/1-memoire/README.md)) |
| `404 Resource Not Found` sur les appels LLM | `AZURE_OPENAI_ENDPOINT` sans `/openai/v1`, ou déploiement inexistant | Corriger l'endpoint ; vérifier le nom de déploiement dans le portail Azure |
| Les tests DB échouent en CI | Schéma non initialisé | Déjà géré : `ci.yml` initialise le schéma avant les tests |

---

**Voir aussi :** [Architecture](architecture.md) · [Chantier 3 — Qualité](chantiers/3-qualite/README.md)

⬆ [Retour à l'index](README.md)
