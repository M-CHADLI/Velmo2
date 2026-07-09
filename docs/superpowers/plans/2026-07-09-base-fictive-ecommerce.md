# Base fictive e-commerce & accès agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Doter Velmo d'une base métier e-commerce fictive (~13 000 lignes) et d'un accès en lecture par tool-calling, pour répondre réellement aux questions de commande.

**Architecture:** Nouveau package `business/` (schéma DDL, modèles Pydantic, assemblage pur, repository lecture, outils LangChain). Un script de seed génère des *pools* via LLM (avec fallback statique) puis assemble à l'échelle de façon déterministe. L'agent passe d'un `llm.invoke` simple à une boucle tool-calling bornée, garde-fous et tracing conservés.

**Tech Stack:** Python 3.12, PostgreSQL (psycopg 3, `dict_row`), LangChain (`langchain_openai.ChatOpenAI`, `langchain_core.tools`), Pydantic v2, pytest, uv.

## Global Constraints

- Environnement géré par **uv** ; exécuter les tests via `uv run pytest`, avec `UV_LINK_MODE=copy` exporté (venv sous OneDrive).
- Accès métier en **lecture seule** — aucune écriture de commande.
- Tables métier **séparées** des tables mémoire ; créées via `init_business_tables(db)` appelée depuis `memory/database.py::init_db()`.
- **Connexion PostgreSQL unique partagée** (`memory/database.py::get_db`), non thread-safe : tous les accès métier restent dans le thread principal (aucune parallélisation).
- **Identifiants alphanumériques préfixés** : client `CLI-` + 6 chiffres (`CLI-000123`) ; commande `CMD-` + 4 chiffres (`CMD-4490`) ; produit `PRD-` + 4 alphanum. (`PRD-A1B2`) ; suivi `FR` + 9 chiffres (`FR123456789`).
- Chaque table a une **UUID PK technique** (`gen_random_uuid()`). Les identifiants de **lookup** sont `UNIQUE` : `customer_ref`, `order_number`, `sku`. `tracking_number` est un attribut d'affichage **non-unique** (jamais utilisé comme clé de recherche) — décision humaine 2026-07-09.
- **Statuts commande** : `en_attente | payée | préparation | expédiée | livrée | annulée`.
- **Statuts livraison** : `en_préparation | en_transit | livré`.
- Les **outils renvoient toujours un texte** (jamais d'exception) ; « introuvable » plutôt qu'une erreur.
- Boucle agent bornée par **`MAX_TOOL_ITERS = 3`** ; garde-fous input/output et tracing LangSmith (`observability.trace_run`) conservés.
- Volume seed par défaut : **1 000 clients**, ratio produits **2:1** (~2 000), commandes **~2,67:1** (~2 667).
- **Tests hermétiques** : DB mockée (MagicMock), LLM stubbé, aucun appel réseau ni Postgres réel.

---

## File Structure

```
business/
  __init__.py       — exports publics
  schema.py         — DDL des 5 tables + init_business_tables(db)
  models.py         — Pydantic : pools LLM (BaseProduct, CityEntry, Pools)
  generate.py       — assemblage pur : formats d'ID + assemble_dataset(...) -> Dataset
  repository.py     — requêtes lecture (db=None)
  tools.py          — outils LangChain + identité (contextvar)
scripts/seed_business_db.py   — pools LLM (+ fallback statique) -> generate -> insert
memory/database.py            — init_db() appelle init_business_tables (MODIFY)
agent/agent.py                — boucle tool-calling (MODIFY)
tests/
  test_business_schema.py
  test_business_generate.py
  test_business_repository.py
  test_business_tools.py
  test_business_seed.py
  test_agent_tool_loop.py
```

---

## Task 1: Schéma des tables métier

**Files:**
- Create: `business/__init__.py`
- Create: `business/schema.py`
- Modify: `memory/database.py` (appeler `init_business_tables` dans `init_db`)
- Test: `tests/test_business_schema.py`

**Interfaces:**
- Produces: `business.schema.init_business_tables(db=None) -> None` ; `business.schema.BUSINESS_DDL: list[str]`

- [ ] **Step 1: Write the failing test**

`tests/test_business_schema.py` :

```python
from unittest.mock import MagicMock
from business.schema import init_business_tables


def _fake_db():
    db = MagicMock()
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db.connect.return_value = conn
    return db, conn, cur


def test_init_business_tables_creates_all_tables():
    db, conn, cur = _fake_db()
    init_business_tables(db=db)
    executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
    for table in ["customers", "products", "orders", "order_items", "shipments"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in executed
    conn.commit.assert_called_once()


def test_init_business_tables_defines_alnum_identifiers():
    db, conn, cur = _fake_db()
    init_business_tables(db=db)
    executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
    assert "customer_ref" in executed and "order_number" in executed
    assert "tracking_number" in executed and "sku" in executed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'business.schema'`

- [ ] **Step 3: Create `business/__init__.py`**

```python
"""Velmo 2.0 — Base métier e-commerce fictive (lecture seule)."""
```

- [ ] **Step 4: Create `business/schema.py`**

```python
import logging

logger = logging.getLogger(__name__)

BUSINESS_DDL = [
    """
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
        velmo_user_id  VARCHAR(100),
        created_at     TIMESTAMP DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);",
    "CREATE INDEX IF NOT EXISTS idx_customers_velmo_user ON customers(velmo_user_id);",
    """
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
    """,
    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);",
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_number   VARCHAR(20) UNIQUE NOT NULL,
        customer_id    UUID NOT NULL REFERENCES customers(customer_id),
        status         VARCHAR(20) NOT NULL,
        total_eur      NUMERIC(10,2) NOT NULL DEFAULT 0,
        placed_at      TIMESTAMP NOT NULL,
        updated_at     TIMESTAMP DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);",
    "CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);",
    """
    CREATE TABLE IF NOT EXISTS order_items (
        item_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id       UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
        product_id     UUID NOT NULL REFERENCES products(product_id),
        quantity       INT NOT NULL CHECK (quantity > 0),
        unit_price_eur NUMERIC(10,2) NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);",
    """
    CREATE TABLE IF NOT EXISTS shipments (
        shipment_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        order_id           UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
        carrier            VARCHAR(40),
        tracking_number    VARCHAR(20),
        status             VARCHAR(20) NOT NULL,
        shipped_at         TIMESTAMP,
        estimated_delivery TIMESTAMP,
        delivered_at       TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);",
]


def init_business_tables(db=None) -> None:
    """Créer les 5 tables métier si absentes. Idempotent."""
    from memory.database import get_db

    db = db or get_db()
    conn = db.connect()
    with conn.cursor() as cur:
        for stmt in BUSINESS_DDL:
            cur.execute(stmt)
    conn.commit()
    logger.info("Business tables initialized.")
```

- [ ] **Step 5: Wire into `memory/database.py`**

Dans `memory/database.py`, méthode `init_db`, juste après l'appel existant `init_guardrail_table(self)` (ligne ~113), ajouter :

```python
                # 6. Create business e-commerce tables (customers, products, orders, ...)
                from business.schema import init_business_tables
                init_business_tables(self)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_schema.py -q`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add business/__init__.py business/schema.py memory/database.py tests/test_business_schema.py
git commit -m "feat(business): schéma des tables métier e-commerce"
```

---

## Task 2: Modèles Pydantic + assemblage déterministe

**Files:**
- Create: `business/models.py`
- Create: `business/generate.py`
- Test: `tests/test_business_generate.py`

**Interfaces:**
- Consumes: rien (task autonome).
- Produces :
  - `business.models.BaseProduct`, `CityEntry`, `Pools` (Pydantic).
  - `business.generate.customer_ref(i:int)->str`, `order_number(i:int)->str`, `product_sku(rng)->str`, `tracking_number(rng)->str`.
  - `business.generate.Dataset` (dataclass : `customers`, `products`, `orders`, `order_items`, `shipments` — chacun `list[dict]`).
  - `business.generate.assemble_dataset(pools: Pools, n_customers: int, *, product_ratio: float = 2.0, order_ratio: float = 2.667, seed: int = 42, demo_user_id: str = "demo_user") -> Dataset`.
  - `business.generate.DEFAULT_POOLS: Pools` (fallback statique).

- [ ] **Step 1: Write the failing test**

`tests/test_business_generate.py` :

```python
from business.models import Pools
from business.generate import (
    assemble_dataset, customer_ref, order_number, DEFAULT_POOLS,
)

FORCED_DEMO_STATUSES = {"préparation", "expédiée", "livrée"}


def test_id_formatters():
    assert customer_ref(123) == "CLI-000123"
    assert order_number(4490) == "CMD-4490"


def test_assemble_counts_and_uniqueness():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=20, seed=1)
    assert len(ds.customers) == 20
    assert len(ds.products) == 40           # ratio 2:1
    assert len(ds.orders) == 53             # round(20 * 2.667)
    # unicité des identifiants métier
    assert len({c["customer_ref"] for c in ds.customers}) == 20
    assert len({c["email"] for c in ds.customers}) == 20
    assert len({p["sku"] for p in ds.products}) == 40
    assert len({o["order_number"] for o in ds.orders}) == len(ds.orders)


def test_demo_user_prelinked_with_status_coverage():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=20, seed=1)
    demo = [c for c in ds.customers if c["velmo_user_id"] == "demo_user"]
    assert len(demo) == 1
    demo_id = demo[0]["customer_id"]
    demo_orders = [o for o in ds.orders if o["customer_id"] == demo_id]
    statuses = {o["status"] for o in demo_orders}
    assert FORCED_DEMO_STATUSES.issubset(statuses)


def test_order_totals_match_items():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=15, seed=2)
    items_by_order = {}
    for it in ds.order_items:
        items_by_order.setdefault(it["order_id"], []).append(it)
    for o in ds.orders:
        items = items_by_order[o["order_id"]]
        assert items, "chaque commande a au moins un article"
        expected = round(sum(i["quantity"] * i["unit_price_eur"] for i in items), 2)
        assert o["total_eur"] == expected


def test_shipment_coherence_with_status():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=25, seed=3)
    ship_by_order = {s["order_id"]: s for s in ds.shipments}
    for o in ds.orders:
        if o["status"] == "annulée":
            assert o["order_id"] not in ship_by_order
        elif o["status"] == "expédiée":
            s = ship_by_order[o["order_id"]]
            assert s["status"] == "en_transit" and s["shipped_at"] is not None
        elif o["status"] == "livrée":
            s = ship_by_order[o["order_id"]]
            assert s["status"] == "livré" and s["delivered_at"] is not None


def test_order_items_reference_existing_products():
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=15, seed=4)
    product_ids = {p["product_id"] for p in ds.products}
    for it in ds.order_items:
        assert it["product_id"] in product_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_generate.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'business.models'`

- [ ] **Step 3: Create `business/models.py`**

```python
from pydantic import BaseModel, Field


class BaseProduct(BaseModel):
    name: str
    category: str
    base_price_eur: float = Field(..., gt=0)
    description: str = ""
    variant_axis: str = "aucun"  # couleur | taille | capacité | aucun


class CityEntry(BaseModel):
    city: str
    zip: str


class Pools(BaseModel):
    base_products: list[BaseProduct]
    first_names: list[str]
    last_names: list[str]
    cities: list[CityEntry]
    carriers: list[str]
```

- [ ] **Step 4: Create `business/generate.py`**

```python
"""Assemblage déterministe d'un jeu de données métier à partir de pools."""
import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import BaseProduct, CityEntry, Pools

_ALNUM = string.ascii_uppercase + string.digits

VARIANT_VALUES = {
    "couleur": ["Noir", "Blanc", "Bleu", "Rouge", "Vert", "Gris"],
    "taille": ["S", "M", "L", "XL"],
    "capacité": ["64 Go", "128 Go", "256 Go", "512 Go"],
    "aucun": [None],
}

ORDER_STATUSES = ["en_attente", "payée", "préparation", "expédiée", "livrée", "annulée"]


# --- Formats d'identifiants (alphanumériques préfixés) -----------------------
def customer_ref(i: int) -> str:
    return f"CLI-{i:06d}"


def order_number(i: int) -> str:
    return f"CMD-{i:04d}"


def product_sku(rng: random.Random) -> str:
    return "PRD-" + "".join(rng.choices(_ALNUM, k=4))


def tracking_number(rng: random.Random) -> str:
    return "FR" + "".join(rng.choices(string.digits, k=9))


@dataclass
class Dataset:
    customers: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    orders: list[dict] = field(default_factory=list)
    order_items: list[dict] = field(default_factory=list)
    shipments: list[dict] = field(default_factory=list)


def _slug_email(first: str, last: str, taken: set[str]) -> str:
    def norm(s: str) -> str:
        return "".join(ch for ch in s.lower() if ch.isalnum())
    base = f"{norm(first)}.{norm(last)}"
    email = f"{base}@example.fr"
    n = 1
    while email in taken:
        n += 1
        email = f"{base}{n}@example.fr"
    taken.add(email)
    return email


def _build_products(pools: Pools, rng: random.Random, target: int) -> list[dict]:
    products: list[dict] = []
    skus: set[str] = set()
    i = 0
    while len(products) < target:
        base: BaseProduct = pools.base_products[i % len(pools.base_products)]
        i += 1
        for variant in VARIANT_VALUES.get(base.variant_axis, [None]):
            if len(products) >= target:
                break
            sku = product_sku(rng)
            while sku in skus:
                sku = product_sku(rng)
            skus.add(sku)
            name = base.name if variant is None else f"{base.name} {variant}"
            price = round(base.base_price_eur * rng.uniform(0.9, 1.15), 2)
            products.append({
                "product_id": str(uuid.uuid4()),
                "sku": sku,
                "name": name,
                "description": base.description,
                "category": base.category,
                "price_eur": price,
                "stock": rng.randint(0, 500),
            })
    return products


def _build_customers(pools: Pools, rng: random.Random, n: int, demo_user_id: str) -> list[dict]:
    customers: list[dict] = []
    emails: set[str] = set()
    for idx in range(n):
        first = rng.choice(pools.first_names)
        last = rng.choice(pools.last_names)
        city: CityEntry = rng.choice(pools.cities)
        customers.append({
            "customer_id": str(uuid.uuid4()),
            "customer_ref": customer_ref(idx + 1),
            "full_name": f"{first} {last}",
            "email": _slug_email(first, last, emails),
            "phone": "0" + "".join(rng.choices(string.digits, k=9)),
            "address_line": f"{rng.randint(1, 200)} rue {rng.choice(pools.last_names)}",
            "city": city.city,
            "zip": city.zip,
            "country": "France",
            "velmo_user_id": demo_user_id if idx == 0 else None,
        })
    return customers


def _shipment_for(order: dict, rng: random.Random, pools: Pools) -> dict | None:
    status = order["status"]
    placed = order["placed_at"]
    if status == "annulée":
        return None
    carrier = rng.choice(pools.carriers)
    base = {
        "shipment_id": str(uuid.uuid4()),
        "order_id": order["order_id"],
        "carrier": carrier,
        "tracking_number": tracking_number(rng),
        "shipped_at": None,
        "estimated_delivery": None,
        "delivered_at": None,
    }
    if status in ("en_attente", "payée", "préparation"):
        base["status"] = "en_préparation"
        base["estimated_delivery"] = placed + timedelta(days=rng.randint(3, 7))
    elif status == "expédiée":
        shipped = placed + timedelta(days=rng.randint(1, 2))
        base["status"] = "en_transit"
        base["shipped_at"] = shipped
        base["estimated_delivery"] = shipped + timedelta(days=rng.randint(2, 4))
    elif status == "livrée":
        shipped = placed + timedelta(days=rng.randint(1, 2))
        delivered = shipped + timedelta(days=rng.randint(1, 4))
        base["status"] = "livré"
        base["shipped_at"] = shipped
        base["delivered_at"] = delivered
        base["estimated_delivery"] = delivered
    return base


def _placed_and_status(rng: random.Random, now: datetime, forced: str | None):
    if forced is not None:
        if forced == "livrée":
            return now - timedelta(days=rng.randint(20, 540)), forced
        if forced == "expédiée":
            return now - timedelta(days=rng.randint(3, 12)), forced
        return now - timedelta(days=rng.randint(0, 4)), forced
    days = rng.randint(0, 540)
    placed = now - timedelta(days=days)
    if days > 20:
        status = "annulée" if rng.random() < 0.1 else "livrée"
    elif days >= 3:
        status = "expédiée"
    else:
        status = rng.choice(["en_attente", "payée", "préparation"])
    return placed, status


def _make_order(customer: dict, products: list[dict], rng: random.Random,
                pools: Pools, now: datetime, counter: int, forced: str | None,
                out: Dataset) -> None:
    placed, status = _placed_and_status(rng, now, forced)
    order = {
        "order_id": str(uuid.uuid4()),
        "order_number": order_number(counter),
        "customer_id": customer["customer_id"],
        "status": status,
        "total_eur": 0.0,
        "placed_at": placed,
    }
    n_items = rng.randint(1, 4)
    chosen = rng.sample(products, k=min(n_items, len(products)))
    total = 0.0
    for prod in chosen:
        qty = rng.randint(1, 3)
        total += qty * prod["price_eur"]
        out.order_items.append({
            "item_id": str(uuid.uuid4()),
            "order_id": order["order_id"],
            "product_id": prod["product_id"],
            "quantity": qty,
            "unit_price_eur": prod["price_eur"],
        })
    order["total_eur"] = round(total, 2)
    out.orders.append(order)
    ship = _shipment_for(order, rng, pools)
    if ship is not None:
        out.shipments.append(ship)


def assemble_dataset(pools: Pools, n_customers: int, *, product_ratio: float = 2.0,
                     order_ratio: float = 2.667, seed: int = 42,
                     demo_user_id: str = "demo_user") -> Dataset:
    rng = random.Random(seed)
    now = datetime(2026, 7, 9)
    ds = Dataset()
    ds.products = _build_products(pools, rng, round(n_customers * product_ratio))
    ds.customers = _build_customers(pools, rng, n_customers, demo_user_id)

    order_target = round(n_customers * order_ratio)
    counter = 1
    demo_customer = ds.customers[0]
    # Commandes forcées du client démo : couverture de statuts
    for forced in ["préparation", "expédiée", "livrée"]:
        _make_order(demo_customer, ds.products, rng, pools, now, counter, forced, ds)
        counter += 1
    # Reste des commandes réparties aléatoirement (distribution "la plupart peu")
    while len(ds.orders) < order_target:
        customer = rng.choice(ds.customers)
        _make_order(customer, ds.products, rng, pools, now, counter, None, ds)
        counter += 1
    return ds


# --- Pools statiques de fallback (hors-ligne) --------------------------------
DEFAULT_POOLS = Pools(
    base_products=[
        BaseProduct(name="T-shirt coton", category="Vêtements", base_price_eur=19.9, variant_axis="couleur"),
        BaseProduct(name="Jean slim", category="Vêtements", base_price_eur=49.9, variant_axis="taille"),
        BaseProduct(name="Casque audio", category="Électronique", base_price_eur=89.0, variant_axis="couleur"),
        BaseProduct(name="Smartphone", category="Électronique", base_price_eur=599.0, variant_axis="capacité"),
        BaseProduct(name="Clé USB", category="Électronique", base_price_eur=12.5, variant_axis="capacité"),
        BaseProduct(name="Mug céramique", category="Maison", base_price_eur=9.9, variant_axis="couleur"),
        BaseProduct(name="Lampe de bureau", category="Maison", base_price_eur=34.0, variant_axis="aucun"),
        BaseProduct(name="Sac à dos", category="Bagagerie", base_price_eur=59.0, variant_axis="couleur"),
    ],
    first_names=["Karim", "Julie", "Ahmed", "Sophie", "Lucas", "Emma", "Yanis",
                 "Léa", "Nabil", "Camille", "Hugo", "Inès", "Théo", "Sarah"],
    last_names=["Martin", "Bernard", "Dubois", "Moreau", "Chadli", "Petit",
                "Roux", "Fontaine", "Girard", "Benali", "Lefebvre", "Nguyen"],
    cities=[CityEntry(city="Paris", zip="75001"), CityEntry(city="Lyon", zip="69003"),
            CityEntry(city="Marseille", zip="13008"), CityEntry(city="Lille", zip="59000"),
            CityEntry(city="Toulouse", zip="31000"), CityEntry(city="Nantes", zip="44000")],
    carriers=["Colissimo", "Chronopost", "Mondial Relay", "DPD"],
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_generate.py -q`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add business/models.py business/generate.py tests/test_business_generate.py
git commit -m "feat(business): modèles + assemblage déterministe des données"
```

---

## Task 3: Repository de lecture

**Files:**
- Create: `business/repository.py`
- Test: `tests/test_business_repository.py`

**Interfaces:**
- Produces :
  - `get_order_by_number(order_number: str, db=None) -> dict | None` — clés : `order_number, status, total_eur, placed_at, items (list[{name, sku, quantity, unit_price_eur}]), shipment (dict|None)`.
  - `get_customer_by_email(email: str, db=None) -> dict | None`
  - `get_customer_by_velmo_user(user_id: str, db=None) -> dict | None`
  - `get_orders_for_customer(customer_id: str, db=None) -> list[dict]` — chaque item : `order_number, status, total_eur, placed_at`.

- [ ] **Step 1: Write the failing test**

`tests/test_business_repository.py` :

```python
from unittest.mock import MagicMock
from business import repository as repo


def _db_with(fetchone_seq, fetchall_seq):
    """Mock db dont le curseur renvoie les valeurs fournies dans l'ordre."""
    cur = MagicMock()
    cur.fetchone.side_effect = list(fetchone_seq)
    cur.fetchall.side_effect = list(fetchall_seq)
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db = MagicMock()
    db.connect.return_value = conn
    return db, cur


def test_get_order_by_number_found_with_items_and_shipment():
    order_row = {"order_id": "o1", "order_number": "CMD-4490",
                 "status": "expédiée", "total_eur": 59.8, "placed_at": "2026-07-01"}
    items = [{"name": "T-shirt coton Noir", "sku": "PRD-A1B2",
              "quantity": 2, "unit_price_eur": 19.9}]
    shipment = {"carrier": "Colissimo", "tracking_number": "FR123456789",
                "status": "en_transit", "shipped_at": "2026-07-02",
                "estimated_delivery": "2026-07-05", "delivered_at": None}
    db, cur = _db_with([order_row, shipment], [items])
    out = repo.get_order_by_number("CMD-4490", db=db)
    assert out["order_number"] == "CMD-4490"
    assert out["items"][0]["sku"] == "PRD-A1B2"
    assert out["shipment"]["tracking_number"] == "FR123456789"


def test_get_order_by_number_not_found_returns_none():
    db, cur = _db_with([None], [])
    assert repo.get_order_by_number("CMD-0000", db=db) is None


def test_get_customer_by_velmo_user():
    db, cur = _db_with([{"customer_id": "c1", "full_name": "Karim Martin",
                         "email": "karim.martin@example.fr"}], [])
    out = repo.get_customer_by_velmo_user("demo_user", db=db)
    assert out["customer_id"] == "c1"


def test_get_orders_for_customer_lists_orders():
    orders = [{"order_number": "CMD-0001", "status": "livrée",
               "total_eur": 19.9, "placed_at": "2026-01-01"}]
    db, cur = _db_with([], [orders])
    out = repo.get_orders_for_customer("c1", db=db)
    assert out[0]["order_number"] == "CMD-0001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_repository.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'business.repository'`

- [ ] **Step 3: Create `business/repository.py`**

```python
"""Requêtes lecture seule sur la base métier (thread principal, connexion partagée)."""


def _conn(db):
    from memory.database import get_db
    db = db or get_db()
    return db.connect()


def get_order_by_number(order_number: str, db=None) -> dict | None:
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT order_id, order_number, status, total_eur, placed_at "
            "FROM orders WHERE order_number = %s",
            (order_number,),
        )
        order = cur.fetchone()
        if not order:
            return None
        cur.execute(
            "SELECT p.name AS name, p.sku AS sku, oi.quantity AS quantity, "
            "oi.unit_price_eur AS unit_price_eur "
            "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
            "WHERE oi.order_id = %s",
            (order["order_id"],),
        )
        items = cur.fetchall()
        cur.execute(
            "SELECT carrier, tracking_number, status, shipped_at, "
            "estimated_delivery, delivered_at FROM shipments WHERE order_id = %s",
            (order["order_id"],),
        )
        shipment = cur.fetchone()
    return {
        "order_number": order["order_number"],
        "status": order["status"],
        "total_eur": float(order["total_eur"]),
        "placed_at": order["placed_at"],
        "items": [dict(it) for it in items],
        "shipment": dict(shipment) if shipment else None,
    }


def get_customer_by_email(email: str, db=None) -> dict | None:
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, full_name, email FROM customers WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_customer_by_velmo_user(user_id: str, db=None) -> dict | None:
    if not user_id:
        return None
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, full_name, email FROM customers "
            "WHERE velmo_user_id = %s LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_orders_for_customer(customer_id: str, db=None, limit: int = 10) -> list[dict]:
    conn = _conn(db)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT order_number, status, total_eur, placed_at FROM orders "
            "WHERE customer_id = %s ORDER BY placed_at DESC LIMIT %s",
            (customer_id, limit),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_repository.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add business/repository.py tests/test_business_repository.py
git commit -m "feat(business): repository lecture seule"
```

---

## Task 4: Outils LangChain + identité

**Files:**
- Create: `business/tools.py`
- Modify: `business/__init__.py` (exports)
- Test: `tests/test_business_tools.py`

**Interfaces:**
- Consumes: `business.repository` (Task 3).
- Produces :
  - `set_business_identity(user_id: str, email: str | None = None) -> None`
  - `get_discovered_email() -> str | None`
  - outils LangChain `lookup_order`, `get_customer_orders` (appelables via `.invoke({...})`).
  - `TOOLS = [lookup_order, get_customer_orders]`

- [ ] **Step 1: Write the failing test**

`tests/test_business_tools.py` :

```python
import business.tools as t


def test_lookup_order_found(monkeypatch):
    monkeypatch.setattr(t.repo, "get_order_by_number", lambda n, db=None: {
        "order_number": "CMD-4490", "status": "expédiée", "total_eur": 59.8,
        "placed_at": "2026-07-01",
        "items": [{"name": "T-shirt coton Noir", "sku": "PRD-A1B2",
                   "quantity": 2, "unit_price_eur": 19.9}],
        "shipment": {"carrier": "Colissimo", "tracking_number": "FR123456789",
                     "status": "en_transit", "shipped_at": "2026-07-02",
                     "estimated_delivery": "2026-07-05", "delivered_at": None},
    })
    out = t.lookup_order.invoke({"order_number": "CMD-4490"})
    assert "CMD-4490" in out and "expédiée" in out and "FR123456789" in out


def test_lookup_order_not_found(monkeypatch):
    monkeypatch.setattr(t.repo, "get_order_by_number", lambda n, db=None: None)
    out = t.lookup_order.invoke({"order_number": "CMD-0000"})
    assert "CMD-0000" in out and "aucune" in out.lower()


def test_lookup_order_never_raises(monkeypatch):
    def boom(n, db=None):
        raise RuntimeError("db down")
    monkeypatch.setattr(t.repo, "get_order_by_number", boom)
    out = t.lookup_order.invoke({"order_number": "CMD-4490"})
    assert isinstance(out, str) and len(out) > 0


def test_get_customer_orders_by_prelinked_identity(monkeypatch):
    monkeypatch.setattr(t.repo, "get_customer_by_velmo_user",
                        lambda uid, db=None: {"customer_id": "c1", "full_name": "Karim",
                                              "email": "k@example.fr"})
    monkeypatch.setattr(t.repo, "get_orders_for_customer",
                        lambda cid, db=None: [{"order_number": "CMD-0001",
                                               "status": "livrée", "total_eur": 19.9,
                                               "placed_at": "2026-01-01"}])
    t.set_business_identity("demo_user")
    out = t.get_customer_orders.invoke({})
    assert "CMD-0001" in out and "livrée" in out


def test_get_customer_orders_by_email_records_identity(monkeypatch):
    monkeypatch.setattr(t.repo, "get_customer_by_email",
                        lambda e, db=None: {"customer_id": "c2", "full_name": "Julie",
                                            "email": e})
    monkeypatch.setattr(t.repo, "get_orders_for_customer",
                        lambda cid, db=None: [])
    t.set_business_identity("demo_user")
    out = t.get_customer_orders.invoke({"email": "julie@example.fr"})
    assert t.get_discovered_email() == "julie@example.fr"
    assert "aucune commande" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_tools.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'business.tools'`

- [ ] **Step 3: Create `business/tools.py`**

```python
"""Outils LangChain de lecture métier + résolution d'identité (contextvar)."""
import logging
from contextvars import ContextVar

from langchain_core.tools import tool

from . import repository as repo

logger = logging.getLogger(__name__)

_identity: ContextVar[dict] = ContextVar("velmo_business_identity", default={})


def set_business_identity(user_id: str, email: str | None = None) -> None:
    _identity.set({"user_id": user_id, "email": email})


def get_discovered_email() -> str | None:
    return _identity.get().get("email")


def _format_order(o: dict) -> str:
    lines = [f"Commande {o['order_number']} — statut : {o['status']} — "
             f"total : {o['total_eur']:.2f} €"]
    for it in o.get("items", []):
        lines.append(f"  • {it['quantity']}× {it['name']} ({it['sku']}) "
                     f"à {it['unit_price_eur']:.2f} €")
    ship = o.get("shipment")
    if ship:
        lines.append(f"Livraison : {ship['status']} via {ship['carrier']} "
                     f"(suivi {ship['tracking_number']})")
        if ship.get("estimated_delivery"):
            lines.append(f"Livraison estimée : {ship['estimated_delivery']}")
    return "\n".join(lines)


@tool
def lookup_order(order_number: str) -> str:
    """Récupère le statut, les articles et la livraison d'une commande par son
    numéro (ex. 'CMD-4490')."""
    try:
        o = repo.get_order_by_number(order_number)
    except Exception as e:  # noqa: BLE001
        logger.error(f"lookup_order failed: {e}")
        return "Impossible de consulter cette commande pour le moment."
    if not o:
        return f"Aucune commande {order_number} trouvée."
    return _format_order(o)


@tool
def get_customer_orders(email: str | None = None) -> str:
    """Liste les commandes d'un client. Si 'email' est fourni, cherche par email ;
    sinon utilise le client relié à l'utilisateur courant."""
    ident = _identity.get()
    try:
        if email:
            customer = repo.get_customer_by_email(email)
            if customer:
                _identity.set({**ident, "email": email})
        else:
            customer = repo.get_customer_by_velmo_user(ident.get("user_id"))
    except Exception as e:  # noqa: BLE001
        logger.error(f"get_customer_orders failed: {e}")
        return "Impossible de consulter les commandes pour le moment."
    if not customer:
        return ("Aucun client identifié. Donnez-moi votre email ou un numéro "
                "de commande (ex. CMD-4490).")
    try:
        orders = repo.get_orders_for_customer(customer["customer_id"])
    except Exception as e:  # noqa: BLE001
        logger.error(f"get_orders_for_customer failed: {e}")
        return "Impossible de consulter les commandes pour le moment."
    if not orders:
        return f"Aucune commande trouvée pour {customer['full_name']}."
    lines = [f"Commandes de {customer['full_name']} :"]
    for o in orders:
        lines.append(f"  • {o['order_number']} — {o['status']} — "
                     f"{float(o['total_eur']):.2f} €")
    return "\n".join(lines)


TOOLS = [lookup_order, get_customer_orders]
```

- [ ] **Step 4: Update `business/__init__.py`**

```python
"""Velmo 2.0 — Base métier e-commerce fictive (lecture seule)."""
from .tools import (
    TOOLS,
    get_customer_orders,
    get_discovered_email,
    lookup_order,
    set_business_identity,
)

__all__ = [
    "TOOLS",
    "lookup_order",
    "get_customer_orders",
    "set_business_identity",
    "get_discovered_email",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_tools.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add business/tools.py business/__init__.py tests/test_business_tools.py
git commit -m "feat(business): outils LangChain + résolution d'identité"
```

---

## Task 5: Script de seed (pools LLM + fallback + insertion)

**Files:**
- Create: `scripts/seed_business_db.py`
- Test: `tests/test_business_seed.py`

**Interfaces:**
- Consumes: `business.models.Pools`, `business.generate.assemble_dataset`, `business.generate.DEFAULT_POOLS`, `business.generate.Dataset`.
- Produces :
  - `generate_pools(settings=None) -> Pools` — appel LLM, fallback `DEFAULT_POOLS` sur erreur.
  - `insert_dataset(ds: Dataset, db=None) -> None` — `TRUNCATE` puis insertion par lots.
  - `seed(n_customers: int = 1000, db=None, settings=None, seed: int = 42) -> Dataset`.

- [ ] **Step 1: Write the failing test**

`tests/test_business_seed.py` :

```python
from unittest.mock import MagicMock
import scripts.seed_business_db as s
from business.generate import DEFAULT_POOLS


def test_generate_pools_falls_back_on_llm_error(monkeypatch):
    class BoomLLM:
        def invoke(self, *a, **k):
            raise RuntimeError("no llm")
    monkeypatch.setattr(s, "_build_llm", lambda settings: BoomLLM())
    pools = s.generate_pools(settings=object())
    assert pools.base_products  # fallback non vide


def test_insert_dataset_truncates_then_inserts():
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db = MagicMock()
    db.connect.return_value = conn
    from business.generate import assemble_dataset
    ds = assemble_dataset(DEFAULT_POOLS, n_customers=5, seed=7)
    s.insert_dataset(ds, db=db)
    executed = " ".join(str(c.args[0]) for c in cur.execute.call_args_list
                        if c.args) + " ".join(
        str(c.args[0]) for c in cur.executemany.call_args_list if c.args)
    assert "TRUNCATE" in executed
    assert cur.executemany.call_count == 5   # 5 tables
    conn.commit.assert_called()


def test_seed_assembles_expected_quotas(monkeypatch):
    monkeypatch.setattr(s, "generate_pools", lambda settings=None: DEFAULT_POOLS)
    monkeypatch.setattr(s, "insert_dataset", lambda ds, db=None: None)
    ds = s.seed(n_customers=5, db=MagicMock(), settings=object())
    assert len(ds.customers) == 5
    assert len(ds.products) == 10
    assert any(c["velmo_user_id"] == "demo_user" for c in ds.customers)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_seed.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.seed_business_db'`

- [ ] **Step 3: Create `scripts/seed_business_db.py`**

```python
"""Génère et insère la base métier fictive.

Usage:
    uv run python scripts/seed_business_db.py --customers 1000
"""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from business.generate import DEFAULT_POOLS, Dataset, assemble_dataset  # noqa: E402
from business.models import Pools  # noqa: E402

logger = logging.getLogger(__name__)

POOLS_PROMPT = (
    "Génère un JSON pour peupler une boutique e-commerce française fictive. "
    "Format STRICT, sans texte autour :\n"
    '{"base_products":[{"name":str,"category":str,"base_price_eur":float,'
    '"description":str,"variant_axis":"couleur|taille|capacité|aucun"}],'
    '"first_names":[str],"last_names":[str],'
    '"cities":[{"city":str,"zip":str}],"carriers":[str]}\n'
    "~100 base_products variés, ~60 first_names, ~60 last_names, ~40 cities FR."
)


def _build_llm(settings):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=settings.azure_openai_deployment_name,
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        temperature=0.7,
    )


def generate_pools(settings=None) -> Pools:
    """Un appel LLM pour des pools riches ; fallback statique sur échec."""
    if settings is None:
        from memory.config import load_settings
        settings = load_settings()
    try:
        llm = _build_llm(settings)
        resp = llm.invoke(POOLS_PROMPT)
        content = resp.content if hasattr(resp, "content") else str(resp)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        pools = Pools(**json.loads(content.strip()))
        if not pools.base_products:
            raise ValueError("pools LLM vides")
        logger.info("Pools générés par LLM.")
        return pools
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Génération LLM échouée ({e}), fallback pools statiques.")
        return DEFAULT_POOLS


def insert_dataset(ds: Dataset, db=None) -> None:
    from memory.database import get_db
    db = db or get_db()
    conn = db.connect()
    with conn.cursor() as cur:
        cur.execute("TRUNCATE order_items, shipments, orders, products, "
                    "customers RESTART IDENTITY CASCADE;")
        cur.executemany(
            "INSERT INTO customers (customer_id, customer_ref, full_name, email, "
            "phone, address_line, city, zip, country, velmo_user_id) "
            "VALUES (%(customer_id)s, %(customer_ref)s, %(full_name)s, %(email)s, "
            "%(phone)s, %(address_line)s, %(city)s, %(zip)s, %(country)s, "
            "%(velmo_user_id)s)", ds.customers)
        cur.executemany(
            "INSERT INTO products (product_id, sku, name, description, category, "
            "price_eur, stock) VALUES (%(product_id)s, %(sku)s, %(name)s, "
            "%(description)s, %(category)s, %(price_eur)s, %(stock)s)", ds.products)
        cur.executemany(
            "INSERT INTO orders (order_id, order_number, customer_id, status, "
            "total_eur, placed_at) VALUES (%(order_id)s, %(order_number)s, "
            "%(customer_id)s, %(status)s, %(total_eur)s, %(placed_at)s)", ds.orders)
        cur.executemany(
            "INSERT INTO order_items (item_id, order_id, product_id, quantity, "
            "unit_price_eur) VALUES (%(item_id)s, %(order_id)s, %(product_id)s, "
            "%(quantity)s, %(unit_price_eur)s)", ds.order_items)
        cur.executemany(
            "INSERT INTO shipments (shipment_id, order_id, carrier, tracking_number, "
            "status, shipped_at, estimated_delivery, delivered_at) "
            "VALUES (%(shipment_id)s, %(order_id)s, %(carrier)s, %(tracking_number)s, "
            "%(status)s, %(shipped_at)s, %(estimated_delivery)s, %(delivered_at)s)",
            ds.shipments)
    conn.commit()
    logger.info("Dataset inséré : %d clients, %d produits, %d commandes.",
                len(ds.customers), len(ds.products), len(ds.orders))


def seed(n_customers: int = 1000, db=None, settings=None, seed: int = 42) -> Dataset:
    pools = generate_pools(settings=settings)
    ds = assemble_dataset(pools, n_customers=n_customers, seed=seed)
    insert_dataset(ds, db=db)
    return ds


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--customers", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    ds = seed(n_customers=args.customers, seed=args.seed)
    print(f"Seed terminé : {len(ds.customers)} clients, {len(ds.products)} produits, "
          f"{len(ds.orders)} commandes.")
```

- [ ] **Step 4: Create `scripts/__init__.py` if missing**

Vérifier l'import `scripts.seed_business_db` : créer `scripts/__init__.py` vide s'il n'existe pas.

```python
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_business_seed.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/seed_business_db.py scripts/__init__.py tests/test_business_seed.py
git commit -m "feat(business): script de seed (pools LLM + fallback + insertion)"
```

---

## Task 6: Boucle tool-calling de l'agent

**Files:**
- Modify: `agent/agent.py`
- Test: `tests/test_agent_tool_loop.py`

**Interfaces:**
- Consumes: `business.tools.TOOLS`, `business.tools.set_business_identity`.
- Produces (nouveaux membres de `VelmoAgent`) :
  - `MAX_TOOL_ITERS = 3` (constante module).
  - `VelmoAgent._execute_tool(self, call: dict) -> str`
  - `VelmoAgent._generate_with_tools(self, messages: list) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_agent_tool_loop.py` :

```python
from langchain_core.messages import AIMessage
from agent.agent import VelmoAgent, MAX_TOOL_ITERS


class StubToolLLM:
    """LLM factice : 1er invoke -> tool_call, 2e invoke -> réponse finale."""
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None):
        msg = self.scripted[min(self.calls, len(self.scripted) - 1)]
        self.calls += 1
        return msg


def _agent_with(stub):
    # évite toute construction réseau/DB : on n'appelle que _generate_with_tools
    agent = VelmoAgent.__new__(VelmoAgent)
    agent.llm = stub
    return agent


def test_tool_loop_executes_tool_then_returns_final(monkeypatch):
    import business.tools as bt
    # exécuter le vrai outil lookup_order avec le repository mocké
    monkeypatch.setattr(bt.repo, "get_order_by_number",
                        lambda n, db=None: {"order_number": n, "status": "expédiée",
                                            "total_eur": 10.0, "placed_at": "x",
                                            "items": [], "shipment": None})
    scripted = [
        AIMessage(content="", tool_calls=[{"name": "lookup_order",
                                           "args": {"order_number": "CMD-4490"},
                                           "id": "call_1"}]),
        AIMessage(content="Votre commande CMD-4490 est expédiée."),
    ]
    agent = _agent_with(StubToolLLM(scripted))
    from langchain_core.messages import SystemMessage, HumanMessage
    msgs = [SystemMessage(content="sys"), HumanMessage(content="où est CMD-4490 ?")]
    out = agent._generate_with_tools(msgs)
    assert out == "Votre commande CMD-4490 est expédiée."


def test_tool_loop_is_bounded():
    # LLM qui demande TOUJOURS un outil -> doit s'arrêter à MAX_TOOL_ITERS
    always_tool = AIMessage(content="partiel",
                            tool_calls=[{"name": "lookup_order",
                                         "args": {"order_number": "CMD-1"},
                                         "id": "c"}])
    import business.tools as bt
    bt_repo_backup = bt.repo.get_order_by_number
    try:
        bt.repo.get_order_by_number = lambda n, db=None: None
        agent = _agent_with(StubToolLLM([always_tool]))
        from langchain_core.messages import HumanMessage
        out = agent._generate_with_tools([HumanMessage(content="x")])
        assert agent.llm.calls <= MAX_TOOL_ITERS
        assert out == "partiel"
    finally:
        bt.repo.get_order_by_number = bt_repo_backup


def test_generate_with_tools_falls_back_without_bind_tools():
    class NoBindLLM:
        def bind_tools(self, tools):
            raise NotImplementedError("no tools")
        def invoke(self, messages, config=None):
            return AIMessage(content="réponse simple")
    agent = _agent_with(NoBindLLM())
    from langchain_core.messages import HumanMessage
    out = agent._generate_with_tools([HumanMessage(content="bonjour")])
    assert out == "réponse simple"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_agent_tool_loop.py -q`
Expected: FAIL — `ImportError: cannot import name 'MAX_TOOL_ITERS' from 'agent.agent'`

- [ ] **Step 3: Add imports and constant to `agent/agent.py`**

En tête de `agent/agent.py`, après les imports existants, ajouter :

```python
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from business.tools import TOOLS, set_business_identity, get_discovered_email
import business.tools as _bt

MAX_TOOL_ITERS = 3
```

- [ ] **Step 4: Add the tool-loop methods to `VelmoAgent`**

Ajouter ces deux méthodes dans la classe `VelmoAgent` (après `__init__`) :

```python
    def _execute_tool(self, call: dict) -> str:
        """Exécuter un tool_call LangChain et renvoyer son texte (jamais lever)."""
        name = call.get("name")
        args = call.get("args", {}) or {}
        tool_map = {t.name: t for t in TOOLS}
        tool = tool_map.get(name)
        if tool is None:
            return f"Outil inconnu : {name}"
        try:
            return tool.invoke(args)
        except Exception as e:  # noqa: BLE001
            return f"Erreur outil {name} : {e}"

    def _generate_with_tools(self, messages: list) -> str:
        """Boucle tool-calling bornée. Retombe sur un invoke simple si le modèle
        ne supporte pas bind_tools."""
        try:
            llm_tools = self.llm.bind_tools(TOOLS)
        except Exception:
            with trace_run("agent_response") as run:
                ai = self.llm.invoke(messages, config=run.config)
            return ai.content if hasattr(ai, "content") else str(ai)

        ai = None
        for _ in range(MAX_TOOL_ITERS):
            with trace_run("agent_response") as run:
                ai = llm_tools.invoke(messages, config=run.config)
            messages.append(ai)
            tool_calls = getattr(ai, "tool_calls", None)
            if not tool_calls:
                break
            for call in tool_calls:
                result = self._execute_tool(call)
                messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        return ai.content if ai is not None and hasattr(ai, "content") else ""
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_agent_tool_loop.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Wire the loop into `process_message`**

Dans `agent/agent.py::process_message`, **remplacer** le bloc « Stage 3: Call DeepSeek » actuel (le `try/except` autour de `self.llm.invoke(full_prompt)`, lignes ~61-74) par :

```python
        # Set identity for business tools (pre-linked lookup by user_id)
        set_business_identity(user_id)

        # Stage 3: Generate response via bounded tool-calling loop
        try:
            messages = [
                SystemMessage(content=f"{system_prompt}\n\nContext:\n{context_str}"),
                HumanMessage(content=message),
            ]
            llm_response = self._generate_with_tools(messages)
        except Exception:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return VelmoResponse(
                allowed=False,
                message="Je ne peux pas traiter cette demande. Je suis l'assistant du support Velmo — reformulez et je vous aide avec plaisir.",
                guard_decision=None,
                memory_context=context,
                turn_number=0,
                latency_ms=latency_ms
            )
```

- [ ] **Step 7: Persist discovered email as a fact (best-effort)**

Dans `process_message`, juste avant « Stage 5: Store in short-term memory », ajouter :

```python
        # Persist any discovered customer email as a durable fact (best-effort)
        discovered = get_discovered_email()
        if discovered:
            try:
                from memory.schema import FactData
                self.memory.long_term.store_fact(
                    user_id=user_id,
                    conversation_id=user_id,
                    fact_data=FactData(key="customer_email", value=discovered,
                                       type="identifier", confidence=1.0,
                                       source="tool_lookup"),
                    extracted_at_msg=0,
                )
            except Exception:
                pass
```

- [ ] **Step 8: Run the full affected suite**

Run: `UV_LINK_MODE=copy uv run pytest tests/test_agent_tool_loop.py tests/test_agent_orchestrator.py tests/test_agent_e2e_guardrails.py -q`
Expected: PASS (les tests orchestrateur existants restent verts ; si un test mockait `self.llm.invoke`, l'adapter pour mocker `bind_tools`/`_generate_with_tools`).

- [ ] **Step 9: Commit**

```bash
git add agent/agent.py tests/test_agent_tool_loop.py
git commit -m "feat(agent): boucle tool-calling avec accès base métier"
```

---

## Task 7: Vérification d'intégration (seed réel + smoke)

**Files:**
- Aucun fichier de code ; étape de validation manuelle documentée.

- [ ] **Step 1: Initialiser le schéma**

Run: `UV_LINK_MODE=copy uv run python -c "from memory import get_db; get_db().init_db(); print('schema ok')"`
Expected: `schema ok` (crée les 5 tables métier).

- [ ] **Step 2: Seed à petit volume**

Run: `UV_LINK_MODE=copy uv run python scripts/seed_business_db.py --customers 50`
Expected: `Seed terminé : 50 clients, 100 produits, ~133 commandes.`

- [ ] **Step 3: Vérifier la pré-liaison et un lookup**

Run:
```bash
UV_LINK_MODE=copy uv run python -c "
from business import repository as r
c = r.get_customer_by_velmo_user('demo_user'); print('demo client:', c['full_name'])
orders = r.get_orders_for_customer(c['customer_id']); print('commandes demo:', len(orders))
print(r.get_order_by_number(orders[0]['order_number']))
"
```
Expected: un client démo, ≥ 3 commandes, et le détail d'une commande avec articles + livraison.

- [ ] **Step 4: Run the whole test suite**

Run: `UV_LINK_MODE=copy uv run pytest -q`
Expected: toute la suite passe (business + observability + guardrails + agent).

- [ ] **Step 5: Commit (si ajustements)**

```bash
git add -A
git commit -m "test(business): vérification d'intégration seed + lookup"
```

---

## Self-Review

**Spec coverage :**
- 5 tables (schéma §1) → Task 1 ✅
- Identifiants alphanumériques → formats dans Task 2, colonnes dans Task 1 ✅
- Génération hybride (pools LLM + assemblage + fallback) → Task 2 (assemblage) + Task 5 (pools LLM/fallback/insertion) ✅
- Statuts + cohérence livraison → Task 2 (`_shipment_for`) ✅
- Pré-liaison `demo_user` + couverture statuts → Task 2 ✅
- Repository lecture → Task 3 ✅
- Outils + identité contextvar + mémorisation email → Task 4 (outils) + Task 6 step 7 (persist fact) ✅
- Boucle tool-calling bornée + garde-fous + tracing + fallback → Task 6 ✅
- Volume 1000 / ratios → Task 2 défauts + Task 5 CLI ✅
- Tests hermétiques → toutes les tasks utilisent mock DB / stub LLM ✅

**Placeholder scan :** aucun TBD/TODO ; tout le code est fourni intégralement.

**Type consistency :** `assemble_dataset(pools, n_customers, *, product_ratio, order_ratio, seed, demo_user_id)` cohérent entre Task 2 (déf.), Task 5 (appel via `seed`). `Dataset` (5 `list[dict]`) cohérent Task 2 ↔ Task 5 `insert_dataset`. Clés de `get_order_by_number` (`order_number, status, total_eur, placed_at, items, shipment`) cohérentes Task 3 ↔ Task 4 `_format_order`. `TOOLS`, `set_business_identity`, `get_discovered_email` cohérents Task 4 ↔ Task 6. `tool_calls` en dicts (`name/args/id`) cohérents avec le stub LLM (Task 6).

**Note d'exécution :** en Task 6 step 8, si des tests d'orchestrateur existants mockaient `self.llm.invoke`, ils doivent être adaptés pour `bind_tools`/`_generate_with_tools` (mentionné explicitement dans l'étape).
