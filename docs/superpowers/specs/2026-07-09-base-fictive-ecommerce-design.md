# Base fictive e-commerce & accès agent — Design

**Date :** 2026-07-09
**Statut :** validé (brainstorming)
**Chantier lié :** Agent principal (memory + guardrails + LLM)

## Objectif

Doter Velmo d'une **base de données métier e-commerce fictive** (~13 000 lignes) et
d'un **accès en lecture par tool-calling**, pour que l'agent réponde réellement aux
questions type « où est ma commande `CMD-4490` ? », « quand serai-je livré ? »,
« qu'ai-je commandé ? ».

## Contexte (état actuel)

- Aucune donnée métier n'existe : pas de table `orders`/`customers`/`products`.
- L'agent (`agent/agent.py`) fait un simple `llm.invoke(prompt)` : **aucun outil**,
  aucune capacité à interroger une base. Le prompt le dit « assistant e-commerce »
  mais il ne peut rien consulter.
- Tables existantes (mémoire/observabilité) : `facts`, `guardrail_log`, `audit_log`,
  `extraction_metadata`. Les nouvelles tables métier sont **séparées** — aucune
  collision.
- La connexion PostgreSQL est un singleton partagé (`memory/database.py::get_db`),
  en `autocommit=False`, **non thread-safe** (voir `docs/OPTIMISATIONS_LATENCE.md`).
  Les nouveaux accès lecture réutilisent ce singleton **dans le thread principal**
  uniquement.

## Décisions de conception

| Sujet | Décision |
|-------|----------|
| Périmètre | Complet : seed + outils agent + identité |
| Entités | Cœur commande : customers, products, orders, order_items, shipments |
| Identité | `demo_user` pré-relié à un client + lookup par n° commande / email |
| Accès agent | Tool-calling LangChain (`bind_tools`), boucle bornée |
| Génération | Hybride : LLM génère des *pools*, le script assemble à l'échelle |
| Volume | 1 000 clients ; proportions produits 2:1 (~2 000), commandes ~2,67:1 (~2 667) |
| Identifiants | Alphanumériques préfixés (`CLI-`, `CMD-`, `PRD-`, suivi `FR…`) |

---

## 1. Schéma de données

Cinq tables, créées par `business/schema.py::init_business_tables(db)`, appelée
depuis `memory/database.py::init_db()` après les tables mémoire.

### Conventions d'identifiants (alphanumériques)

| Entité | Colonne métier | Format | Exemple |
|--------|----------------|--------|---------|
| Client | `customer_ref` | `CLI-` + 6 chiffres | `CLI-000123` |
| Commande | `order_number` | `CMD-` + 4–5 chiffres | `CMD-4490` |
| Produit | `sku` | `PRD-` + 4 alphanum. | `PRD-A1B2` |
| Livraison (suivi) | `tracking_number` | `FR` + 9 chiffres | `FR123456789` |

Chaque table garde en plus une **UUID PK technique** (`gen_random_uuid()`), les
identifiants métier ci-dessus étant `UNIQUE`.

### DDL

```sql
CREATE TABLE IF NOT EXISTS customers (
    customer_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_ref   VARCHAR(20) UNIQUE NOT NULL,
    full_name      VARCHAR(120) NOT NULL,
    email          VARCHAR(160) UNIQUE NOT NULL,
    phone          VARCHAR(30),
    address_line   VARCHAR(200),
    city           VARCHAR(80),
    zip            VARCHAR(10),
    country        VARCHAR(60) DEFAULT 'France',
    velmo_user_id  VARCHAR(100),            -- pré-liaison chat -> client (NULL si non lié)
    created_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customers_velmo_user ON customers(velmo_user_id);

CREATE TABLE IF NOT EXISTS products (
    product_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku            VARCHAR(20) UNIQUE NOT NULL,
    name           VARCHAR(160) NOT NULL,
    description    TEXT,
    category       VARCHAR(80),
    price_eur      NUMERIC(10,2) NOT NULL,
    stock          INT DEFAULT 0,
    created_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

CREATE TABLE IF NOT EXISTS orders (
    order_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number   VARCHAR(20) UNIQUE NOT NULL,
    customer_id    UUID NOT NULL REFERENCES customers(customer_id),
    status         VARCHAR(20) NOT NULL,     -- en_attente|payée|préparation|expédiée|livrée|annulée
    total_eur      NUMERIC(10,2) NOT NULL DEFAULT 0,
    placed_at      TIMESTAMP NOT NULL,
    updated_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);

CREATE TABLE IF NOT EXISTS order_items (
    item_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id       UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id     UUID NOT NULL REFERENCES products(product_id),
    quantity       INT NOT NULL CHECK (quantity > 0),
    unit_price_eur NUMERIC(10,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id           UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    carrier            VARCHAR(40),          -- Colissimo|Chronopost|Mondial Relay|DPD
    tracking_number    VARCHAR(20),
    status             VARCHAR(20) NOT NULL, -- en_préparation|en_transit|livré
    shipped_at         TIMESTAMP,
    estimated_delivery TIMESTAMP,
    delivered_at       TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
```

### Cohérence statut ↔ livraison (règle dérivée)

| Statut commande | Livraison associée |
|-----------------|--------------------|
| `en_attente`, `payée`, `préparation` | `shipments.status = en_préparation`, pas de `shipped_at` |
| `expédiée` | `en_transit`, `shipped_at` renseigné, `estimated_delivery` futur |
| `livrée` | `livré`, `delivered_at` renseigné |
| `annulée` | aucune ligne `shipments` |

---

## 2. Génération des données — hybride LLM + assemblage

Script : `scripts/seed_business_db.py`. Volume paramétrable par CLI
(`--customers 1000`), défauts : 1 000 clients, ratio produits 2:1, commandes 2,67:1.

### Étape A — pools riches (un seul appel LLM)

Le LLM configuré (`ChatOpenAI`, même endpoint que l'agent) produit **un JSON** de
*pools*, validé par Pydantic (`business/models.py`), avec réparation sur échec de
parse (nettoyage des fences ```` ```json ````, retry ×2 — même pattern que
`memory/judge.py`). Contenu demandé :

- `base_products` : ~100 produits de base (`name`, `category`, `base_price_eur`,
  `description`, `variant_axis` ∈ {couleur, taille, capacité, aucun}).
- `first_names`, `last_names` : ~60 chacun (FR).
- `cities` : ~40 villes FR avec `zip`.
- `carriers` : liste de transporteurs.

Si l'appel LLM échoue (réseau/clé), **fallback** sur des pools statiques minimaux
intégrés au script, pour que le seed reste exécutable hors-ligne.

### Étape B — assemblage déterministe (Python, `random.Random(seed)` fixe)

1. **Produits** (~2 000) : pour chaque `base_product`, générer des variantes selon
   `variant_axis` (ex. couleur × taille) jusqu'à atteindre le quota ; `sku`
   `PRD-` + 4 alphanum. uniques ; `price_eur` = `base_price` ± variation ;
   `stock` aléatoire.
2. **Clients** (1 000) : `customer_ref` `CLI-` + compteur zéro-paddé ; `full_name`
   = prénom + nom tirés des pools ; `email` dérivé du nom (unicité garantie par
   suffixe) ; ville/zip tirés des pools. **Un client à index fixe reçoit
   `velmo_user_id = 'demo_user'`** (pré-liaison).
3. **Commandes** (~2 667) : réparties sur les clients (distribution : la plupart
   1–3 commandes, quelques-uns plus). Chaque commande : `order_number`
   `CMD-` + numéro croissant ; `placed_at` sur les 18 derniers mois ; `status`
   tiré selon l'ancienneté (anciennes → `livrée`, récentes → `préparation`/`expédiée`) ;
   **1–4 `order_items`** (produits distincts, quantités 1–3) ; `total_eur` =
   Σ(`quantity` × `unit_price_eur`) ; `shipments` dérivé selon la règle statut ci-dessus.
4. Le **client `demo_user`** reçoit un jeu garanti de commandes couvrant plusieurs
   statuts (préparation, expédiée, livrée) pour une démo complète immédiate.

### Idempotence

`--reset` (défaut activé) : `TRUNCATE order_items, shipments, orders, products,
customers RESTART IDENTITY CASCADE` avant insertion. Insertion par lots
(`executemany`) dans une transaction.

---

## 3. Accès agent — tool-calling

### 3.1 Repository (`business/repository.py`)

Fonctions pures de lecture (thread principal, connexion singleton). Retournent des
`dict` sérialisables :

```python
def get_order_by_number(order_number: str, db=None) -> dict | None
def get_customer_by_email(email: str, db=None) -> dict | None
def get_customer_by_velmo_user(user_id: str, db=None) -> dict | None
def get_orders_for_customer(customer_id: str, db=None) -> list[dict]
```

`get_order_by_number` inclut les `order_items` (avec nom produit) et la `shipment`
associée (statut, transporteur, suivi, ETA).

### 3.2 Outils LangChain (`business/tools.py`)

Deux `@tool` (schéma Pydantic auto), avec **résolution d'identité** :

```python
@tool
def lookup_order(order_number: str) -> str:
    """Récupère le statut, les articles et la livraison d'une commande par son
    numéro (ex. 'CMD-4490'). Renvoie un texte lisible ou 'commande introuvable'."""

@tool
def get_customer_orders(email: str | None = None) -> str:
    """Liste les commandes d'un client. Si 'email' est fourni, cherche par email ;
    sinon utilise le client relié à l'utilisateur courant (contextvar)."""
```

- L'**identité courante** (`user_id`, et l'email éventuellement découvert) est portée
  par une **contextvar** (`business/tools.py`), positionnée par l'agent au début du
  tour — même mécanisme que `observability.set_user_context`.
- `get_customer_orders(email=...)` qui trouve un client → l'agent **mémorise** l'email
  comme fact (`key=customer_email`) via la mémoire existante, pour les tours suivants.
- Les outils renvoient toujours un **texte** (jamais d'exception) : « introuvable »
  plutôt qu'une erreur, pour ne pas casser la boucle.

### 3.3 Boucle de l'agent (`agent/agent.py`)

`process_message` devient une boucle tool-calling bornée :

```
set_user_context(user_id) + set_business_identity(user_id)
input guard  ── bloqué ? → réponse safe
llm_with_tools = self.llm.bind_tools([lookup_order, get_customer_orders])
messages = [system, ...contexte mémoire..., user]
for i in range(MAX_TOOL_ITERS = 3):
    ai = llm_with_tools.invoke(messages, config=trace_run(...).config)
    if not ai.tool_calls: break
    for call in ai.tool_calls:
        result = execute_tool(call)          # texte
        messages.append(ToolMessage(result, tool_call_id=call.id))
    messages.append(ai)
output guard sur ai.content ── bloqué ? → réponse safe
store + judge (inchangé)
```

- **Garde-fous conservés** : input avant la boucle, output sur la réponse finale.
- **Tracing LangSmith** : chaque `invoke` de la boucle est tracé (`trace_run`),
  scores latence inchangés.
- **Borne** `MAX_TOOL_ITERS = 3` : au-delà, on sort et on répond avec ce qu'on a
  (évite les boucles infinies et borne la latence).
- **Fail-safe** : toute exception dans la boucle → message safe existant, comme aujourd'hui.
- **Fallback sans tool-calling** : si le modèle configuré ne supporte pas les outils,
  `bind_tools` est encapsulé dans un try/except qui retombe sur l'ancien chemin
  `llm.invoke(prompt)`.

---

## 4. Découpage fichiers

```
business/
  __init__.py       — exports
  schema.py         — DDL + init_business_tables(db)
  models.py         — Pydantic : pools LLM + lignes assemblées
  repository.py     — requêtes lecture
  tools.py          — outils LangChain + identité (contextvar)
scripts/seed_business_db.py   — génération hybride + seed
memory/database.py            — init_db() appelle init_business_tables
agent/agent.py                — boucle tool-calling
tests/
  test_business_repository.py
  test_business_tools.py
  test_agent_tool_loop.py
```

## 5. Tests

- **Repository** (`test_business_repository.py`) : sur un petit jeu seedé connu —
  `get_order_by_number` (trouvé / introuvable, items + shipment présents),
  `get_customer_by_email`, `get_orders_for_customer`, `get_customer_by_velmo_user`.
- **Outils** (`test_business_tools.py`) : `lookup_order` (texte lisible / introuvable),
  `get_customer_orders` par email et via identité pré-reliée (contextvar), non-levée
  d'exception sur entrée inconnue.
- **Boucle agent** (`test_agent_tool_loop.py`) : LLM **stubbé** déterministe — 1ᵉʳ
  `invoke` renvoie un `tool_call` `lookup_order`, 2ᵉ renvoie la réponse finale ;
  vérifie que l'outil est exécuté, le `ToolMessage` réinjecté, la borne
  `MAX_TOOL_ITERS` respectée, et les garde-fous appelés.
- **Seed** : test léger de l'assemblage (`--customers 5`) vérifiant les quotas,
  l'unicité des identifiants, la cohérence statut↔livraison et la pré-liaison
  `demo_user`. Pas d'appel LLM réel en test (pools statiques de fallback).

## 6. Hors périmètre (YAGNI)

- Écritures métier (créer/annuler une commande) — lecture seule.
- Retours (`returns`) et factures (`invoices`) — reportés (option « Étendu » écartée).
- Authentification réelle — l'identité est déclarative (email/n° fournis).
- Pagination des résultats d'outils — les listes sont bornées (top N commandes récentes).

## 7. Risques & points d'attention

- **Latence** : le tool-calling ajoute 1 aller-retour LLM par itération (~1–4 s).
  Borné par `MAX_TOOL_ITERS = 3` et tracé dans LangSmith.
- **Support tool-calling du modèle** : `model-router` et les modèles GPT/Claude
  déployés le supportent ; fallback prévu sinon (§3.3).
- **Génération LLM des pools** : validée Pydantic + fallback statique → le seed
  n'échoue jamais faute de LLM.
- **Connexion partagée** : les lectures métier restent dans le thread principal
  (pas de parallélisation) pour respecter la limite psycopg documentée.
