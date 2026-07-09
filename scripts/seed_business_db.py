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
