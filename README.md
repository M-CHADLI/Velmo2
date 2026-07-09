# 🤖 Velmo 2.0 - Support Agent IA

Velmo 2.0 est un **agent d'assistance client IA** avec **mémoire intelligente**, **garde-fous de sécurité**, et **interface Streamlit** complète.

---

## 🚀 **Quick Start (30 secondes)**

```bash
# 1. Cloner et installer
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2

# 2. Setup complet (dependencies + DB + services)
make setup

# 3. Lancer l'app
make streamlit
```

Ouvre **http://localhost:8501** et commence à chatter! 💬

---

## 📋 **Commandes Principales**

```bash
make help              # Voir toutes les commandes
make streamlit         # 🎯 Lancer le chat
make test              # ✅ Lancer les tests
make format            # 🎨 Formater le code
make clean             # 🗑️ Nettoyer les caches
```

---

## 🏗️ **Architecture**

Velmo 2.0 = **3 Chantiers**

### **Chantier 1: Mémoire (80%)**
- Court-terme: fenêtre glissante 30 messages
- Long-terme: PostgreSQL + pgvector (facts extraction)
- Judge Agent: extrait facts avec Kimi 2.6

### **Chantier 2: Garde-Fous (95%)**
- Input guards: bloque haine, violence, injection prompt, secrets
- Output guards: redaction PII, compliance checks
- Kimi classifier: analyse sémantique

### **Chantier 3: Observabilité (0%)**
- LangFuse tracing
- KPI dashboards
- CI/CD pipeline
- *À implémenter*

---

## 📁 **Structure du Projet**

```
Velmo2/
├── memory/                 🧠 Mémoire agent
│   ├── short_term.py      Fenêtre glissante
│   ├── long_term.py       Storage PostgreSQL
│   ├── judge.py           Judge agent (Kimi)
│   └── manager.py         Orchestration
│
├── guardrails/            🛡️ Sécurité
│   ├── classifier.py      Kimi classifier
│   ├── input_guard.py     Validation entrée
│   ├── output_guard.py    PII redaction
│   └── manager.py         Pipeline
│
├── agent/                 🤖 Agent principal
│   └── agent.py           Chat orchestration
│
├── streamlit/             💬 Interface web
│   ├── app_streamlit.py   Chat app
│   ├── components/        Composants UI
│   └── utils/             Helpers
│
├── tests/                 ✅ Tests
│   └── test_*.py          Unit tests
│
├── eval/                  📊 Évaluation
│   ├── memory_cases.jsonl
│   ├── guardrail_cases.jsonl
│   └── quality_cases.jsonl
│
├── Makefile               📜 Commandes dev
├── docker-compose.yml     🐳 Services
├── pyproject.toml         📦 Dépendances
└── .env.example           ⚙️ Config
```

---

## 🔧 **Setup Détaillé**

### **Prérequis**
- Python ≥ 3.11
- Docker & Docker Compose
- Git

### **Installation Complète**

```bash
# 1. Cloner
git clone https://github.com/M-CHADLI/Velmo2.git
cd Velmo2

# 2. Installer dépendances
pip install -e .

# 3. Démarrer Docker (PostgreSQL + Redis)
docker-compose up -d

# 4. Initialiser DB
python -c "from memory import get_db; get_db().init_db()"

# 5. Lancer Streamlit
streamlit run streamlit/app_streamlit.py
```

**Ou en une commande:**
```bash
make setup && make streamlit
```

---

## 📊 **Configuration Requise**

Créer `.env` à la racine:

```env
# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/velmo

# Redis (optional, for rate limiting)
REDIS_URL=redis://localhost:6379/0

# Azure OpenAI (Kimi 2.6)
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=Kimi-K2.6
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# OpenAI (for embeddings)
OPENAI_API_KEY=your-key-here

# LangFuse (optional, for monitoring)
LANGFUSE_PUBLIC_KEY=your-key
LANGFUSE_SECRET_KEY=your-key
LANGFUSE_HOST=https://cloud.langfuse.com
```

Voir `.env.example` pour la liste complète.

---

## 🎯 **Features**

✅ **Chat en Temps Réel**
- Histamine de messages
- Réponses rapides
- Handling d'erreurs

✅ **Sécurité**
- Protection input (haine, violence, sexuel, injection prompt)
- Redaction PII (cartes, IBAN, passwords)
- Audit trail GDPR

✅ **Mémoire Intelligente**
- Extraction automatique de facts
- Retrieval sémantique
- Persistance long-terme

✅ **Tests & Qualité**
- 2/2 tests passants
- 425 LOC nouveau code
- Architecture propre

---

## 📈 **État d'Avancement**

| Chantier | Status | % | Tâches |
|----------|--------|---|--------|
| **Chantier 1: Mémoire** | 🟡 Avancé | 80% | 9/9 complètées |
| **Chantier 2: Garde-fous** | ✅ Quasi-fini | 95% | 8/8 modules |
| **Chantier 3: Observabilité** | ❌ À faire | 0% | LangFuse, CI/CD |

---

## 🧪 **Tests**

```bash
# Lancer les tests
make test

# Ou directement
pytest tests/ -v

# Watch mode
make test-watch
```

**Résultats:** 2/2 passing ✅

---

## 📚 **Documentation**

- **[streamlit/README.md](streamlit/README.md)** - Interface chat
- **[DEBRIEF_COMPLET.md](DEBRIEF_COMPLET.md)** - Vue globale détaillée
- **[docs/superpowers/](docs/superpowers/)** - Plans & specs d'implémentation

---

## 🐳 **Docker Compose**

**Services inclus:**
- **PostgreSQL 16** + pgvector (port 5432)
- **Redis** Alpine (port 6379)

```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Logs
docker-compose logs -f
```

---

## 🔍 **Troubleshooting**

### **"Database connection error"**
```bash
docker-compose up -d
python -c "from memory import get_db; get_db().init_db()"
```

### **"Module not found"**
```bash
pip install -e .
```

### **"Streamlit not found"**
```bash
pip install streamlit>=1.28.0
```

### **Port 8501 already in use**
```bash
streamlit run streamlit/app_streamlit.py --server.port 8502
```

---

## 🚀 **Déploiement**

### **Local Development**
```bash
make streamlit
```

### **Docker**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "streamlit/app_streamlit.py"]
```

### **Streamlit Cloud**
1. Push vers GitHub
2. https://streamlit.io/cloud
3. Connecter le repo

---

## 📞 **Support**

- 📧 **Issues:** GitHub Issues
- 💬 **Chat:** Utilise Velmo! 🤖
- 📖 **Docs:** Voir dossiers `docs/` et `chantier-*/`

---

## 📜 **Licence**

MIT - Libre d'utilisation

---

## 🎉 **Créé avec**

- 🐍 Python 3.11+
- 🤖 Kimi 2.6 (Azure OpenAI)
- 🎨 Streamlit
- 💾 PostgreSQL + pgvector
- 🧪 Pytest
- 🛡️ Pydantic
- 🔗 LangChain

---

**Prêt? Fais `make setup` et commence! 🚀**
