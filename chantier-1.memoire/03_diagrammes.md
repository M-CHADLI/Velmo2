# Diagrammes — Chantier 1 : Mémoire

**Visualisations** de l'architecture et des flux du Chantier 1.

---

## Architecture — Vue d'ensemble

```mermaid
graph TB
    subgraph ShortTerm["Couche 1: Court terme (100k tokens)"]
        Window["Fenêtre glissante<br/>(messages bruts)"]
    end
    
    subgraph Judge["Couche 2: Judge (tous 10 msgs)"]
        JudgeAgent["Judge Agent<br/>(extraction LLM)"]
        Embedding["Embedding<br/>(vectorization)"]
    end
    
    subgraph LongTerm["Couche 3: Long terme (persistant)"]
        RelDB["Base relationnelle<br/>(faits + métadonnées)"]
        VecDB["Base vectorielle<br/>(embeddings)"]
    end
    
    Input["Message utilisateur"]
    LLM["LLM Principal"]
    Output["Réponse utilisateur"]
    
    Input -->|Ajout| Window
    Window -->|Tous 10 msgs| JudgeAgent
    JudgeAgent -->|Faits structurés| Embedding
    Embedding -->|Persist| RelDB
    Embedding -->|Vectors| VecDB
    
    LLM -.->|Requête vectorielle| VecDB
    VecDB -.->|Top-N faits| LLM
    RelDB -.->|Injection prompt| LLM
    
    LLM --> Output
    
    style ShortTerm fill:#e8f4f8
    style Judge fill:#fff4e6
    style LongTerm fill:#e8f5e9
```

---

## Flux par tour (détaillé)

```mermaid
sequenceDiagram
    actor User
    participant ShortMem as Fenêtre<br/>court terme
    participant Judge as Judge<br/>Agent
    participant RelDB as Base<br/>relationnelle
    participant VecDB as Base<br/>vectorielle
    participant LLM as LLM<br/>Principal
    
    User->>ShortMem: Message N
    Note over ShortMem: Ajout message N<br/>Check budget?
    
    alt Tous les 10 messages
        ShortMem->>Judge: Lit 10 messages + faits existants
        Judge->>Judge: Extract + synchronise
        Judge->>VecDB: Embed et stocke vecteurs
        VecDB->>RelDB: Persist faits+metadata
    end
    
    Note over RelDB,VecDB: Avant appel LLM
    LLM->>VecDB: Requête: "Quels faits pertinents ?"
    VecDB-->>LLM: Top-N (triés par score)
    
    LLM->>RelDB: Fetch faits pour contexte
    RelDB-->>LLM: Faits (status=active)
    
    LLM->>LLM: Génère réponse<br/>(avec contexte injecté)
    
    LLM-->>User: Réponse
    LLM->>ShortMem: Ajout réponse (si espace)
    
    Note over ShortMem: Budget > 80% ?<br/>Si oui: anciens tours s'effacent
```

---

## Fenêtre glissante (FIFO)

```mermaid
graph LR
    subgraph Tour1["Tour 1"]
        M1U["U: Bonjour, je suis Karim"]
        M1A["A: Bienvenue!"]
    end
    
    subgraph Tour2["Tour 2"]
        M2U["U: Facture?"]
        M2A["A: Cherche..."]
    end
    
    subgraph TourN["Tour 30"]
        MNU["U: ..."]
        MNA["A: ..."]
    end
    
    subgraph TourN1["Tour 31 (nouveau)"]
        MN1U["U: Rappelle contrat"]
        MN1A["A: Voir mémoire!"]
    end
    
    Budget["Budget: 100k tokens"]
    
    Tour1 -->|Ajouter| Tour2
    Tour2 -->|Ajouter| TourN
    TourN -->|Ajouter| TourN1
    
    Budget -.->|Si > 80%, Tour 1 sort| Out["(Archivé par Judge)"]
    
    style Tour1 fill:#ffcccc,opacity:0.6
    style TourN1 fill:#ccffcc
    style Out fill:#f0f0f0
```

---

## Judge — Extraction et synchronisation

```mermaid
graph TB
    Input["10 messages bruts<br/>+ faits existants"]
    
    Judge["Judge Agent<br/>(LLM)"]
    
    Decision{{"Nouveau fait ou<br/>mise à jour?"}}
    
    Create["Créer nouveau fait<br/>+ fact_id + confidence"]
    Update["Mettre à jour<br/>+ version_history"]
    Confirm["Confirmer existant"]
    
    Extract["Extraire champs<br/>type, source, sensitivity"]
    
    Embed["Embedding<br/>(Text → Vector)"]
    
    Persist["Persister en base<br/>+ horodatage"]
    
    Input --> Judge
    Judge --> Decision
    Decision -->|Nouveau| Create
    Decision -->|Existing| Update
    Decision -->|Inchangé| Confirm
    
    Create --> Extract
    Update --> Extract
    Confirm --> Extract
    
    Extract --> Embed
    Embed --> Persist
    
    style Judge fill:#fff4e6
    style Decision fill:#ffe0b2
    style Embed fill:#b3e5fc
```

---

## Recherche vectorielle (avant LLM)

```mermaid
graph LR
    Message["Message utilisateur<br/>'Rappelle mon contrat'"]
    
    Embed["Embedding<br/>(Text → Vector)"]
    
    Query["Requête vectorielle<br/>(cosine similarity)"]
    
    VecDB["Base vectorielle<br/>(user_id namespace)"]
    
    Results["Résultats triés<br/>par pertinence"]
    
    Select["Sélection Top-N<br/>(budget tokens)"]
    
    Filter["Filtre: status=active<br/>Exclus: soft_deleted"]
    
    Inject["Injection dans prompt<br/>LLM"]
    
    Message --> Embed
    Embed --> Query
    Query --> VecDB
    VecDB --> Results
    Results --> Select
    Select --> Filter
    Filter --> Inject
    
    style VecDB fill:#b3e5fc
    style Inject fill:#c8e6c9
```

---

## Droit à l'oubli (R5) — Suppression

```mermaid
graph TB
    Request["User demande:<br/>'Oublie mon contrat'"]
    
    Extract["Agent extrait:<br/>key='contract_number'"]
    
    Query["Requête:<br/>SELECT * FROM facts<br/>WHERE key=?"]
    
    SoftDelete["Soft-delete:<br/>UPDATE status='soft_deleted'<br/>SET deletion_reason=..."]
    
    VecDB["Mettre à jour<br/>Base vectorielle<br/>(marquer supprimé)"]
    
    Filter["Recherches futures:<br/>FILTER status='active'<br/>→ Fait n'apparaît plus"]
    
    Confirm["User: 'Confirmé,<br/>oublié!'"]
    
    Request --> Extract
    Extract --> Query
    Query --> SoftDelete
    SoftDelete --> VecDB
    VecDB --> Filter
    Filter --> Confirm
    
    style SoftDelete fill:#ffcccc
    style Filter fill:#ccffcc
```

---

## Isolation stricte (R3)

```mermaid
graph TB
    User1["User: karim_123"]
    User2["User: alice_456"]
    
    subgraph Karim["Collection karim_123"]
        KB["Base: users_karim_123_facts"]
        KV["Vector: namespace=karim_123"]
    end
    
    subgraph Alice["Collection alice_456"]
        AB["Base: users_alice_456_facts"]
        AV["Vector: namespace=alice_456"]
    end
    
    Block1["❌ Karim accède alice?<br/>Bloqué: user_id mismatch"]
    Block2["❌ Requête cross-namespace?<br/>Bloqué au VectorDB"]
    
    User1 -->|READ| Karim
    User2 -->|READ| Alice
    User1 -.->|DENIED| Alice
    User2 -.->|DENIED| Karim
    
    Karim -.-> Block1
    Alice -.-> Block2
    
    style Karim fill:#e3f2fd
    style Alice fill:#f3e5f5
    style Block1 fill:#ffcdd2
    style Block2 fill:#ffcdd2
```

---

## Historique des versions (monitoring)

```mermaid
graph TB
    V1["Version 1<br/>contract_number='KX-4471'<br/>Message: 1<br/>Confidence: 0.99"]
    
    V2["Version 2<br/>contract_number='KX-9999'<br/>Message: 42<br/>Confidence: 0.95<br/>Reason: user_update"]
    
    V3["Version 3<br/>contract_number='KX-8888'<br/>Message: 87<br/>Confidence: 0.92<br/>Reason: correction"]
    
    Current["ACTUEL<br/>KX-8888<br/>(Version 3)"]
    
    V1 -->|Update| V2
    V2 -->|Update| V3
    V3 -->|=| Current
    
    Note1["Judge extrait<br/>message 1"]
    Note2["Judge détecte<br/>changement"]
    Note3["Judge confirme<br/>nouvelle valeur"]
    
    V1 -.-> Note1
    V2 -.-> Note2
    V3 -.-> Note3
    
    History["Version history<br/>conserve V2 + V3<br/>+ Current"]
    
    V1 -.->|Ancienne version| History
    V2 -.->|Archivée| History
    V3 -.->|Courante| History
    
    style V1 fill:#ffebee,opacity:0.5
    style V2 fill:#fff3e0
    style V3 fill:#e8f5e9
    style Current fill:#c8e6c9
```

---

## Interaction mémoire ↔ LLM principal

```mermaid
graph TB
    LLM["LLM Principal"]
    
    Context["Construction contexte"]
    
    subgraph Memory["Mémoire"]
        Window["Fenêtre glissante<br/>(derniers N tours)"]
        Facts["Faits injectés<br/>(top-N pertinents)"]
    end
    
    Prompt["Prompt final<br/>───────────────<br/>Système: instructions<br/>───────────────<br/>Contexte utilisateur: [facts]<br/>───────────────<br/>Conversation: [window]<br/>───────────────<br/>Message courant"]
    
    Response["Réponse<br/>(avec référence<br/>aux faits)"]
    
    LLM --> Context
    Context --> Memory
    Window --> Prompt
    Facts --> Prompt
    Prompt --> LLM
    LLM --> Response
    
    style Memory fill:#e1f5fe
    style Prompt fill:#f5f5f5
    style Facts fill:#fff9c4
```

---

## Machine à états — Cycle de vie d'un fait

```mermaid
stateDiagram-v2
    [*] --> ACTIVE: Judge extrait<br/>(new fact)
    
    ACTIVE --> ACTIVE: Judge met à jour<br/>(version_history++)
    ACTIVE --> SOFT_DELETED: User demande<br/>suppression
    
    SOFT_DELETED --> SOFT_DELETED: Archived<br/>(n'apparaît plus<br/>en recherche)
    
    SOFT_DELETED --> [*]: Audit trail<br/>conservé
    
    note right of ACTIVE
        status = 'active'
        Retourné par recherche
        Injecté dans prompts
    end note
    
    note right of SOFT_DELETED
        status = 'soft_deleted'
        deletion_reason rempli
        Filtré des recherches
        Conservé pour audit
    end note
```

---

**Diagrammes exportables** : voir `/diagrams/` pour fichiers Mermaid bruts.

**Version** : 1.0  
**Date** : 30 juin 2026
