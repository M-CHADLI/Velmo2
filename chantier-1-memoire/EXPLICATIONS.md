# Documentation Pédagogique - Chantier 1: Architecture Mémoire (Velmo 2.0)

Ce document détaille étape par étape les choix d'architecture, l'implémentation et le raisonnement ("Pourquoi") derrière la reconstruction du système de mémoire de Velmo 2.0.

---

## Sommaire
1. [Étape 1 : Analyse des exigences et choix du "All-in-One" pgvector](#étape-1--analyse-des-exigences-et-choix-du-all-in-one-pgvector)
2. [Étape 2 : Configuration de l'infrastructure (Docker, Redis, PostgreSQL)](#étape-2--configuration-de-linfrastructure-docker-redis-postgresql)
3. [Étape 3 : Mémoire à court terme (Fenêtre glissante)](#étape-3--mémoire-à-court-terme-fenêtre-glissante)
4. [Étape 4 : Le Judge Agent (Extraction intelligente des faits)](#étape-4--le-judge-agent-extraction-intelligente-des-faits)
5. [Étape 5 : Mémoire à long terme (PostgreSQL + pgvector, Isolation et Versionnage)](#étape-5--mémoire-à-long-terme-postgresql--pgvector-isolation-et-versionnage)
6. [Étape 6 : Droit à l'oubli (RGPD) et Traçabilité (Audit Trail)](#étape-6--droit-à-loubli-rgpd-et-traçabilité-audit-trail)
7. [Étape 7 : Harnais d'évaluation et robustesse aux accents](#étape-7--harnais-dévaluation-et-robustesse-aux-accents)

---

### Étape 1 : Analyse des exigences et choix du "All-in-One" pgvector

#### Qu'a-t-on fait ?
Nous avons analysé les exigences réglementaires et techniques (R1 à R6) et décidé de consolider l'intégralité du stockage long terme dans une unique base de données relationnelle **PostgreSQL** équipée de l'extension **pgvector**.

#### Pourquoi ?
1. **Isolation stricte (R3) et Transactions ACID** : En combinant les données structurées des faits (JSONB) et les vecteurs (pgvector) dans la même ligne de table, nous éliminons le risque de désynchronisation entre un index vectoriel externe (ex. Pinecone) et notre base relationnelle.
2. **Conformité RGPD (R5)** : Supprimer ou anonymiser des données dans un outil tiers externe de recherche vectorielle en temps réel est complexe et sujet à des délais de cohérence. Avec pgvector, un simple `UPDATE` ou `DELETE` SQL garantit une suppression immédiate et atomique du texte et du vecteur associé.
3. **Simplicité opérationnelle** : Un seul service à maintenir au lieu de deux.

---

### Étape 2 : Configuration de l'infrastructure (Docker, Redis, PostgreSQL)

#### Qu'a-t-on fait ?
- Création du fichier [docker-compose.yml](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/docker-compose.yml).
- Lancement de PostgreSQL 16 avec `pgvector` préinstallé et de Redis (pour le cache/rate limit à venir dans le Chantier 2).
- Création du script d'initialisation de schéma automatique dans [database.py](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/memory/database.py) créant l'extension `vector` et les tables `facts`, `extraction_metadata` et `audit_log`.

#### Pourquoi ?
- L'utilisation de conteneurs Docker standardise l'environnement de développement pour toute l'équipe.
- Automatiser l'activation de `CREATE EXTENSION IF NOT EXISTS vector;` et la création des tables au démarrage garantit que l'application s'auto-configure sans action manuelle requise du développeur.

---

### Étape 3 : Mémoire à court terme (Fenêtre glissante)

#### Qu'a-t-on fait ?
Implémentation de `SlidingWindowMemory` dans [short_term.py](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/memory/short_term.py) qui conserve un historique en mémoire vive des $N$ derniers messages (maximum 30 messages pour 15 tours).

#### Pourquoi ?
- **Tenir le fil de la conversation immédiate (R1)** : Le LLM a besoin de l'historique brut immédiat pour comprendre des références comme "Et l'autre ?" ou "Il grésille un peu".
- **Contrôler le budget de tokens (R4)** : Sans fenêtre glissante (par exemple en envoyant tout l'historique de 100 messages), nous risquons de dépasser les limites de contexte du LLM ou d'exploser les coûts de requêtes.

---

### Étape 4 : Le Judge Agent (Extraction intelligente des faits)

#### Qu'a-t-on fait ?
Création du `JudgeAgent` dans [judge.py](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/memory/judge.py) orchestré avec LangChain et Kimi 2.6. Toutes les 10 interactions (5 tours), les 10 derniers messages lui sont envoyés pour extraire des faits structurés sous format JSON.

#### Pourquoi ?
- Nous ne voulons pas surcharger la base de données ou générer des embeddings coûteux à chaque message. Effectuer l'extraction de manière asynchrone / groupée toutes les 10 interactions est un excellent compromis performance/coût.
- Le Judge filtre le bruit (salutations, questions éphémères) pour n'extraire que les informations à haute valeur (ex. n° de contrat, tutoiement).

---

### Étape 5 : Mémoire à long terme (PostgreSQL + pgvector, Isolation et Versionnage)

#### Qu'a-t-on fait ?
Implémentation dans [long_term.py](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/memory/long_term.py) des mécanismes suivants :
1. **Recherche sémantique** : Vectorisation des requêtes et recherche de similarité cosinus (`<=>`) filtrée par `user_id`.
2. **Versionnage** : Si un fait avec la même clé (ex. `preference`) est ré-extrait avec une nouvelle valeur, l'ancienne valeur est archivée dans un tableau JSONB `version_history` (historique limité aux 3 dernières versions) et la version est incrémentée.
3. **Résilience (Mock Fallback)** : En cas d'erreur de clé d'API OpenAI pour les embeddings, un fallback génère des vecteurs déterministes normalisés à partir du texte pour éviter de planter l'application.

#### Pourquoi ?
- **Isolation stricte (R3)** : La clause SQL `WHERE user_id = %s` est obligatoire et systématique sur toutes les requêtes.
- **Éviter les doublons contradictoires** : Si l'utilisateur dit d'abord "Tutoyez-moi" puis "Veuillez me vouvoyer", nous devons mettre à jour l'information plutôt que d'avoir deux faits contradictoires en base. L'historique des versions préserve la traçabilité en cas d'audit.

---

### Étape 6 : Droit à l'oubli (RGPD) et Traçabilité (Audit Trail)

#### Qu'a-t-on fait ?
- Ajout de `delete_fact_gdpr` dans [long_term.py](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/memory/long_term.py) pour marquer un fait comme `soft_deleted` et enregistrer le motif de sa suppression.
- Intégration dans `VelmoMemoryManager` d'un scan automatique des expressions comme "oublie mon adresse" pour déclencher la suppression en base.
- Enregistrement systématique dans la table `audit_log` de chaque action critique (`fact_extracted`, `fact_accessed`, `fact_updated`, `fact_soft_delete`).

#### Pourquoi ?
- **Droit à l'oubli (R5)** : Supprimer physiquement ou logiquement les données de manière traçable est une obligation légale RGPD/CNIL. Le `soft-delete` permet de cacher définitivement l'information au LLM tout en gardant une trace légale cryptée ou archivée que l'action d'effacement a bien eu lieu.
- **Traçabilité (R6)** : L'audit trail permet de prouver à tout moment comment et quand une donnée client a été collectée ou modifiée.

---

### Étape 7 : Harnais d'évaluation et robustesse aux accents

#### Qu'a-t-on fait ?
Création du script [eval_memory.py](file:///c:/Users/mr%20mehdi/OneDrive/AI%20ENGINEER/Repository/Velmo2/eval_memory.py) simulant le jeu de données fourni. Les assertions ont été équipées d'une fonction de normalisation de texte via `unicodedata` pour retirer les accents et standardiser la casse (ex. normaliser "français" et "francais" pour qu'ils matchent).

#### Pourquoi ?
- Sans normalisation Unicode, les tests d'évaluation échouaient sur des variations mineures d'accents orthographiques introduites naturellement par le LLM (ex: "français" généré vs "francais" attendu dans le fichier de test).
- Le harnais d'évaluation automatisé est la clé de voûte de l'approche MLOps (Chantier 3) pour détecter instantanément toute régression de comportement.
