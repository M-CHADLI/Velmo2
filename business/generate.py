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


# --- Formats d'identifiants (alphanumériques préfixés) -----------------------
def _uuid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128)))


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
                "product_id": _uuid(rng),
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
            "customer_id": _uuid(rng),
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
        "shipment_id": _uuid(rng),
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
        "order_id": _uuid(rng),
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
            "item_id": _uuid(rng),
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
