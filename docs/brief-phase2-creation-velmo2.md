[📖 Documentation](README.md) › Le brief (énoncé)

# Brief de création : Velmo 2.0 — reconstruire l'agent de zéro (mémoire, garde-fous & MLOps)

**Pratique — conception & création**, démarche guidée + tests d'acceptance fournis · trois chantiers regroupés : mémoire, garde-fous, évaluation & MLOps.

Brief rattaché à la SP « Fiabiliser un agent au sein d'un flux de travail métier » — cible la **Phase 2** du parcours.

## Référentiels

[2023] Certification RNCP37827 — Développeur en intelligence artificielle. Compétences transversales.

## Ressources

- Un repo squelette neuf (`velmo-v2/`) : structure de dossiers posée, interface de conversation branchée, mais `memory/`, `guardrails/` et `mlops/` **vides** à concevoir et construire.
- La note de recommandations de l'expert technique (`docs/reco_expert.md`) : **stack imposée** (LLM via API, base relationnelle pour l'état, base vectorielle pour la mémoire long terme, CI GitHub Actions) et exigences de qualité.
- Un jeu de cas mémoire (`eval/memory_cases.jsonl`) : conversations multi-tours et multi-sessions à rejouer.
- Une liste de contenus interdits et un jeu de prompts hostiles (`eval/guardrail_cases.jsonl`) : messages haineux, violents, sexuels, injections de prompt, tentatives de fuite de données.
- Un template de chaîne CI (`.github/workflows/quality.yml`).
- Les fiches et schémas produits aux briefs préparatoires 1 (mémoire & garde-fous) et 2 (évaluation & MLOps).

## Contexte du projet

L'agent de support de Velmo a été rafistolé plusieurs fois (vous l'avez vous-même réparé au brief de remédiation). Mais le code est devenu illisible, la mémoire tient avec de la ficelle et les garde-fous sont posés au petit bonheur. Le comité de direction de Velmo a fait auditer le projet par un expert technique externe. Son verdict : **on ne rapièce plus, on fait table rase et on repart de zéro sur des bases saines.**

L'expert a remis une note de recommandations (`docs/reco_expert.md`) : une stack imposée et **trois exigences non négociables** pour le nouvel agent Velmo 2.0 :

1. **Une mémoire exemplaire** — l'agent doit être remarquablement bon pour se souvenir des conversations, sur un même échange comme d'une session à l'autre.
2. **Des garde-fous sérieux** — plus aucun dérapage : ni en entrée, ni en sortie.
3. **De la qualité mesurée en continu** — on doit pouvoir prouver, à chaque version, que l'agent ne régresse pas (évaluation + MLOps).

**Votre mission :** reconstruire Velmo 2.0 de zéro, à la hauteur de ces trois exigences.

---

## Travail préliminaire de conception (à valider avant tout code — porte d'entrée du brief)

La conception se mène en trois chantiers. Traitez les questions de chacun et produisez le schéma associé.

### Chantier 1 — Mémoire

L'expert impose les exigences suivantes ; à vous d'en déduire l'architecture mémoire (aucune solution n'est imposée, seulement le résultat attendu) :

| # | Exigence imposée |
|---|------------------|
| **R1** | Tenir le fil d'une conversation d'au moins **30 tours** sans perdre une information donnée au tout début. |
| **R2** | Se souvenir, d'une session à l'autre (des jours plus tard), des faits et préférences durables d'un même utilisateur (ex. « je suis client pro », « tutoie-moi », n° de contrat). |
| **R3** | **Isolation stricte** : la mémoire d'un utilisateur n'est jamais accessible à un autre. |
| **R4** | Tenir la fenêtre de contexte : au-delà d'un budget de tokens défini, résumer / sélectionner sans perdre l'information critique. |
| **R5** | **Droit à l'oubli (RGPD)** : un utilisateur peut demander d'oublier une information (« oublie mon numéro de commande »), avec suppression effective et vérifiable. |
| **R6** | **Traçabilité** : on doit pouvoir inspecter ce que l'agent a retenu d'un utilisateur. |

**Questions pour guider votre réflexion (mémoire) :**
- Quels types de mémoire distinguez-vous (court terme de conversation, long terme persistant, mémoire de travail) ? Lequel répond à quelle exigence (R1–R6) ?
- Comment structurez-vous la mémoire long terme : épisodique (que s'est-il passé) vs sémantique (faits durables sur l'utilisateur) ? Quel schéma de données (clé-valeur de préférences, faits typés, embeddings + métadonnées) ?
- Comment décidez-vous ce qui mérite d'être retenu durablement vs ce qui reste éphémère ? Qui écrit en mémoire long terme, et quand ?
- Comment tenez-vous R4 : résumé glissant, sélection des souvenirs pertinents par recherche, troncature ? Comment évitez-vous de résumer en perdant une info critique ?
- Comment implémentez-vous concrètement R5 (suppression) et R3 (isolation par utilisateur) dans votre schéma de stockage ?

### Chantier 2 — Garde-fous

Velmo 2.0 ne doit jamais produire ni laisser passer certaines choses. **Catégories à bloquer (en entrée et en sortie) :**

- contenus haineux, discriminatoires, harcèlement ;
- violence, menaces, incitation à se faire du mal ou à nuire ;
- contenus sexuels / NSFW ;
- données personnelles sensibles en sortie (numéros de carte, mots de passe, données d'autres clients) ;
- sorties hors périmètre (conseil juridique ou médical, propos engageant Velmo au-delà du support) ;
- injections de prompt / tentatives de contournement des consignes (« ignore tes instructions… ») ;
- fuite de secrets ou de configuration interne.

**Questions pour guider votre réflexion (garde-fous) :**
- Où placez-vous chaque contrôle : garde-fou d'entrée (filtrer/neutraliser la requête) et garde-fou de sortie (filtrer la réponse du modèle) ? Lesquels vont aux deux endroits ?
- Quelle méthode par catégorie : liste de blocage / motifs (regex pour les PII), classifieur de modération, modération par LLM, vérification de périmètre ? Quels avantages et angles morts ?
- Comment gérez-vous les faux positifs (bloquer à tort un message légitime) ? Quel équilibre entre sécurité et utilité ?
- Que fait l'agent quand il bloque : quel message poli à l'utilisateur, quelle journalisation, quelle escalade (vers un humain) pour les cas graves ?
- Comment résistez-vous à une injection de prompt qui essaie de désactiver vos garde-fous ?

### Chantier 3 — Évaluation & MLOps

L'agent doit prouver sa **non-régression** à chaque version.

**Questions pour guider votre réflexion (évaluation & MLOps) :**
- Quelles suites d'évaluation : une pour la mémoire (rejouer `memory_cases.jsonl`), une pour les garde-fous (taux de blocage sur `guardrail_cases.jsonl` + taux de faux positifs), une pour la qualité générale ?
- Quelles métriques et quelle note globale comparable d'une version à l'autre ? Quel seuil de blocage de la livraison (et comment éviter de bloquer pour du bruit) ?
- Qu'est-ce qu'une version de Velmo 2.0 (prompt + config mémoire + config garde-fous) ? Où stockez-vous la note de chaque version ?
- Quels signaux de monitorage en exploitation : note mémoire, taux de blocage garde-fous, taux de faux positifs, latence, coût par conversation ?

### Architecture / schéma attendus

- Un **schéma d'architecture global** de Velmo 2.0 : entrée → garde-fou d'entrée → mémoire (lecture) → LLM → garde-fou de sortie → mémoire (écriture) → réponse.
- Le **modèle de données de la mémoire** (court terme + long terme, champs, isolation par utilisateur, suppression).
- Le **tableau des garde-fous** : catégorie × emplacement (entrée/sortie) × méthode × action en cas de blocage.
- Le **schéma de la boucle qualité** : suites d'évaluation → CI (seuil bloquant) → versionnage → signaux de suivi.

**Livrable de conception :** dossier de conception (schéma global + modèle mémoire + tableau des garde-fous + schéma de boucle qualité), validé par le formateur avant tout code.

---

## Démarche imposée (étape par étape)

### Chantier Mémoire
1. Implémenter la mémoire de court terme (fil de conversation, tenue de la fenêtre de contexte R1/R4).
2. Implémenter la mémoire de long terme persistante et isolée par utilisateur (R2/R3), avec écriture sélective des faits durables.
3. Implémenter le droit à l'oubli (R5) et l'inspection de la mémoire d'un utilisateur (R6).

### Chantier Garde-fous
4. Implémenter le garde-fou d'entrée (haine, violence, sexuel, injection de prompt) avec message de refus + journalisation.
5. Implémenter le garde-fou de sortie (mêmes catégories + fuite de PII / secrets + hors périmètre).

### Chantier Évaluation & MLOps
6. Écrire les suites d'évaluation mémoire, garde-fous (blocage + faux positifs) et qualité, et produire une **note globale**.
7. Brancher l'évaluation dans la CI (`quality.yml`) avec blocage sous le seuil ; versionner l'agent et journaliser la note.
8. Exposer les signaux de suivi dans un rapport (`mlops/report.md`).

---

## Tests d'acceptance fournis (la réalisation doit les faire passer)

### Mémoire
- Étant donné une conversation de **30+ tours**, quand on interroge l'agent sur une information donnée au 1er tour, alors il la restitue correctement.
- Étant donné un utilisateur revenant une nouvelle session plus tard, quand il reprend l'échange, alors l'agent se souvient de ses faits/préférences durables.
- Étant donné deux utilisateurs différents, quand ils conversent, alors aucune information de l'un n'apparaît chez l'autre (isolation).
- Étant donné une demande « oublie mon numéro de commande », quand elle est traitée, alors l'information est effectivement supprimée et ne ressort plus.

### Garde-fous
- Étant donné un message haineux, violent ou sexuel, quand il est envoyé, alors l'agent bloque, répond un refus poli et journalise l'événement.
- Étant donné une injection de prompt (« ignore tes instructions et… »), quand elle est envoyée, alors l'agent ne désobéit pas à ses consignes.
- Étant donné une réponse du modèle contenant une donnée sensible (n° de carte), quand elle est produite, alors le garde-fou de sortie l'empêche de sortir.
- Étant donné un message légitime du support, quand il est envoyé, alors il n'est pas bloqué à tort (faux positif sous le seuil défini).

### Évaluation & MLOps
- Étant donné les trois suites, quand l'évaluation s'exécute, alors une note globale et des notes mémoire / garde-fous / qualité sont produites et versionnées.
- Étant donné une régression (mémoire long terme désactivée, ou garde-fou retiré), quand la CI s'exécute, alors la note chute et la livraison est bloquée.
- Étant donné une exécution, quand on ouvre `mlops/report.md`, alors note mémoire, taux de blocage, taux de faux positifs, latence et coût y figurent.

---

## Modalités pédagogiques

Travail en équipe de 2 à 3. 5 jours (35h). Présentiel. Le brief se déroule en deux temps : d'abord la conception, ensuite le développement.

- **Conception (≈ jour 1).** Avant toute ligne de code, l'équipe pense chacun des trois chantiers. Elle traite les questions du Travail préliminaire de conception et produit le dossier de conception (schéma d'architecture global, modèle de données de la mémoire, tableau des garde-fous, schéma de la boucle qualité). Ce dossier est la **porte d'entrée du brief** : il est validé par le formateur avant de passer au code.
- **Développement (≈ jours 2 à 5).** Une fois la conception validée, l'équipe répartit les trois chantiers et les construit selon la Démarche imposée, avec :
  - un stand-up quotidien (avancement par chantier, blocages, dépendances) ;
  - un point d'intégration à mi-parcours (J3) où les trois chantiers se branchent ensemble ;
  - une démo de fin de phase : mémoire multi-session, messages hostiles bloqués en live, puis dégradation volontaire de l'agent montrant la CI qui bloque.

## Modalités d'évaluation

- Validation du dossier de conception (porte d'entrée du brief) : les trois schémas sont questionnés.
- Passage des tests d'acceptance fournis (mémoire + garde-fous + MLOps) + revue de code.
- Auto-évaluation et co-évaluation Simplonline.

## Livrables

- Dossier de conception (schéma global + modèle mémoire + tableau des garde-fous + schéma de boucle qualité).
- Le code de Velmo 2.0 : `memory/` (court + long terme, isolation, oubli), `guardrails/` (entrée + sortie), `mlops/` (suites d'évaluation + CI + versionnage).
- Le rapport de suivi `mlops/report.md`.
- La preuve d'exécution des tests d'acceptance.

## Critères de performance

- Tous les tests d'acceptance fournis passent (mémoire, garde-fous, évaluation/MLOps).
- La mémoire respecte les six exigences imposées (R1–R6), isolation et droit à l'oubli démontrés.
- Aucune des catégories interdites ne passe, en entrée comme en sortie, avec un taux de faux positifs sous le seuil défini.
- Une régression sur la mémoire ou les garde-fous bloque effectivement la livraison.
- Les choix d'architecture (type de mémoire, méthodes de garde-fous) sont justifiés dans le dossier de conception.

## Compétences visées (avec niveau)

| Code | Compétence | Niveau |
|------|-----------|--------|
| C8 | Paramétrer un service d'IA à partir de sa documentation (mémoire, modération) | 1 |
| C15 | Concevoir le cadre technique de l'application (mémoire, garde-fous, MLOps) | 1 |
| C16 | Coordonner la réalisation technique (trois chantiers) | 1 |
| C17 | Développer les composants techniques (mémoire, garde-fous, agent) | 2 |
| C11 | Monitorer un modèle d'IA (signaux de suivi) | 1 |
| C12 | Programmer les tests automatisés d'un modèle d'IA | 1 |
| C13 | Créer une chaîne de livraison continue du modèle (MLOps) | 1 |
| C21 | Mettre en production / résoudre / documenter | 2 |
| CT1 | Planifier le travail en équipe | 2 |
| CT2 | Contribuer au pilotage de l'organisation du travail | 1-2 |
| CT4 | Mettre en œuvre une démarche méthodique de résolution | 2 |
| CT5 | Partager la solution (documentation) | 2 |
| CT8 | Interagir dans un contexte professionnel | 2 |

---

⬆ [Retour à l'index](README.md)
